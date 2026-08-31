"""Rule-based AML/APU-PPT screening thresholds (FR-4).

Deliberately simple, explainable rules rather than a black box — a compliance
officer needs to be able to say *why* a transaction was flagged without
reference to the LLM at all. The LLM layer (app/agents) only adds a
plain-language rationale and a second-pass sanity check on top of these.
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Flag, Transaction

LARGE_AMOUNT_THRESHOLD = 100_000_000.0  # IDR 100,000,000 single-transaction threshold
FREQUENCY_WINDOW = timedelta(hours=24)
FREQUENCY_COUNT_THRESHOLD = 5  # >5 transactions by the same customer in 24h
DEVIATION_MULTIPLIER = 4.0  # amount > 4x the customer's historical average


@dataclass
class ScreeningResult:
    rule_triggered: str
    detail: str


def screen_transaction(db: Session, txn: Transaction) -> list[ScreeningResult]:
    results: list[ScreeningResult] = []

    if txn.amount >= LARGE_AMOUNT_THRESHOLD:
        results.append(ScreeningResult(
            rule_triggered="large_amount",
            detail=f"Transaction amount {txn.amount:,.0f} exceeds single-transaction threshold {LARGE_AMOUNT_THRESHOLD:,.0f}",
        ))

    window_start = txn.timestamp - FREQUENCY_WINDOW
    recent_count = (
        db.query(func.count(Transaction.id))
        .filter(
            Transaction.customer_ref == txn.customer_ref,
            Transaction.timestamp >= window_start,
            Transaction.timestamp <= txn.timestamp,
        )
        .scalar()
    )
    if recent_count and recent_count > FREQUENCY_COUNT_THRESHOLD:
        results.append(ScreeningResult(
            rule_triggered="high_frequency",
            detail=f"{recent_count} transactions by this customer within 24h (threshold {FREQUENCY_COUNT_THRESHOLD})",
        ))

    avg_amount = (
        db.query(func.avg(Transaction.amount))
        .filter(Transaction.customer_ref == txn.customer_ref, Transaction.id != txn.id)
        .scalar()
    )
    if avg_amount and avg_amount > 0 and txn.amount > avg_amount * DEVIATION_MULTIPLIER:
        results.append(ScreeningResult(
            rule_triggered="profile_deviation",
            detail=f"Amount {txn.amount:,.0f} is {txn.amount / avg_amount:.1f}x this customer's historical average ({avg_amount:,.0f})",
        ))

    return results


def screen_unflagged_transactions(db: Session) -> list[Flag]:
    """Runs rule screening (FR-4) + the LangGraph screening/reviewer agents
    (FR-5, FR-6) over every transaction that doesn't already have a flag,
    and persists a Flag for each triggered rule. Called from a compliance
    officer-triggered endpoint and from the seed/demo script.
    """
    from app.agents.graph import run_screening_agent
    from app.services.audit import write_audit

    already_flagged_txn_ids = {row[0] for row in db.query(Flag.transaction_ref).distinct()}
    candidates = db.query(Transaction).filter(~Transaction.id.in_(already_flagged_txn_ids)).all() if already_flagged_txn_ids else db.query(Transaction).all()

    created: list[Flag] = []
    for txn in candidates:
        rule_results = screen_transaction(db, txn)
        if not rule_results:
            continue

        summary = f"amount={txn.amount:,.0f} type={txn.type} timestamp={txn.timestamp.isoformat()}"
        rationale, reviewer_verdict = run_screening_agent(summary, rule_results)

        flag = Flag(
            transaction_ref=txn.id,
            rule_triggered=", ".join(r.rule_triggered for r in rule_results),
            agent_rationale=rationale,
            reviewer_verdict=reviewer_verdict,
        )
        db.add(flag)
        db.commit()
        db.refresh(flag)
        write_audit(db, actor="screening_agent", action="flag_created", entity_ref=flag.id, rationale=rationale)
        created.append(flag)

    return created
