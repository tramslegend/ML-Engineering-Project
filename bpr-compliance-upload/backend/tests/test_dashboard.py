import uuid
from datetime import datetime

from app.models import Customer, Flag, FlagStatus, LoanDecision, Role, Transaction, User
from app.services.audit import write_audit
from app.services.dashboard import build_dashboard_summary


def _user(db, role: Role) -> User:
    u = User(
        name="Dash Test",
        role=role,
        auth_provider_id=f"dashtest-{uuid.uuid4().hex[:8]}",
        hashed_password="x",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _flagged_transaction(db, status: FlagStatus):
    cust = Customer(pseudonymized_id=f"DASH-{uuid.uuid4().hex[:8]}")
    db.add(cust)
    db.commit()
    db.refresh(cust)
    txn = Transaction(customer_ref=cust.id, amount=999.0, type="transfer_out", timestamp=datetime.utcnow(), source_file="t")
    db.add(txn)
    db.commit()
    db.refresh(txn)
    flag = Flag(transaction_ref=txn.id, rule_triggered="large_amount", status=status)
    db.add(flag)
    db.commit()
    return txn, flag


def test_compliance_officer_summary_counts_open_and_escalated(db):
    _flagged_transaction(db, FlagStatus.open)
    _flagged_transaction(db, FlagStatus.escalated)

    user = _user(db, Role.compliance_officer)
    summary = build_dashboard_summary(db, user)

    assert summary.role == Role.compliance_officer
    assert summary.open_flags_count >= 1
    assert summary.escalated_count >= 1
    assert summary.flags_by_status.open >= 1
    assert summary.flags_by_status.escalated >= 1


def test_loan_officer_summary_scoped_to_own_decisions(db):
    user = _user(db, Role.loan_officer)
    other = _user(db, Role.loan_officer)
    cust = Customer(pseudonymized_id=f"DASH-{uuid.uuid4().hex[:8]}")
    db.add(cust)
    db.commit()
    db.refresh(cust)

    db.add(LoanDecision(customer_ref=cust.id, committee_notes="approved by me", decision="approved", decided_by=user.id))
    db.add(LoanDecision(customer_ref=cust.id, committee_notes="approved by other", decision="approved", decided_by=other.id))
    db.commit()

    summary = build_dashboard_summary(db, user)
    assert summary.recent_decisions_count == 1
    assert len(summary.recent_decisions) == 1
    assert summary.recent_decisions[0].decided_by == user.id


def test_auditor_summary_counts_total_entries(db):
    write_audit(db, actor="tester", action="dash_test_action")
    user = _user(db, Role.auditor)
    summary = build_dashboard_summary(db, user)
    assert summary.total_audit_entries >= 1
