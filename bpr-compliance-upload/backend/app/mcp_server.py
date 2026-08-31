"""FastMCP read-only tool boundary. Per the PRD's architecture (agent layer
in a private subnet, only reaching data through a tool boundary with
"no write access to core banking data"), the agent layer never gets a raw
SQLAlchemy session — it calls these read-only tools instead. This server
holds the only DB credential the agent process needs.

Run standalone with: python -m app.mcp_server
"""
from fastmcp import FastMCP

from app.db import SessionLocal
from app.models import Customer, LoanDecision, Transaction

mcp = FastMCP("bpr-compliance-readonly")


@mcp.tool()
def get_customer_transactions(pseudonymized_id: str, limit: int = 50) -> list[dict]:
    """Read-only: list a customer's transactions by pseudonymized_id, newest first."""
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.pseudonymized_id == pseudonymized_id).first()
        if not customer:
            return []
        rows = (
            db.query(Transaction)
            .filter(Transaction.customer_ref == customer.id)
            .order_by(Transaction.timestamp.desc())
            .limit(limit)
            .all()
        )
        return [
            {"id": t.id, "amount": t.amount, "type": t.type, "timestamp": t.timestamp.isoformat()}
            for t in rows
        ]
    finally:
        db.close()


@mcp.tool()
def get_period_summary(period: str) -> dict:
    """Read-only: aggregate transaction and loan-decision facts for a report
    period (YYYY-MM), used by the report-drafting agent so every generated
    figure links back to source records (FR-9)."""
    from sqlalchemy import func

    db = SessionLocal()
    try:
        year, month = (int(p) for p in period.split("-"))
        txn_count = db.query(func.count(Transaction.id)).filter(
            func.extract("year", Transaction.timestamp) == year,
            func.extract("month", Transaction.timestamp) == month,
        ).scalar()
        txn_total = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            func.extract("year", Transaction.timestamp) == year,
            func.extract("month", Transaction.timestamp) == month,
        ).scalar()
        loan_count = db.query(func.count(LoanDecision.id)).filter(
            func.extract("year", LoanDecision.timestamp) == year,
            func.extract("month", LoanDecision.timestamp) == month,
        ).scalar()
        return {
            "period": period,
            "transaction_count": txn_count or 0,
            "transaction_total_amount": float(txn_total or 0.0),
            "loan_decision_count": loan_count or 0,
        }
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
