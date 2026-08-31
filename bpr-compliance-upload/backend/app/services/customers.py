import uuid

from sqlalchemy.orm import Session

from app.models import Customer, Flag, Transaction
from app.schemas import CustomerHistoryOut


def get_customer_history(db: Session, customer_ref: str) -> CustomerHistoryOut | None:
    """Loan officer persona need (PRD §4): quick lookup of a customer's flag
    history. Accepts either the customer's internal id or their
    pseudonymized_id, since the loan-decision form only ever collects the
    latter from an operator in practice.

    Customer.id is a native Postgres UUID column, so passing a non-UUID
    string (e.g. a pseudonymized_id, or partial/garbage input while a user is
    still typing) straight into an `id == customer_ref` comparison raises a
    DB-level cast error rather than just not matching — branch on whether
    customer_ref actually parses as a UUID before querying by id.
    """
    customer = None
    try:
        uuid.UUID(customer_ref)
        customer = db.query(Customer).filter(Customer.id == customer_ref).first()
    except ValueError:
        pass
    if not customer:
        customer = db.query(Customer).filter(Customer.pseudonymized_id == customer_ref).first()
    if not customer:
        return None

    transactions = (
        db.query(Transaction)
        .filter(Transaction.customer_ref == customer.id)
        .order_by(Transaction.timestamp.desc())
        .all()
    )
    tx_ids = [t.id for t in transactions]
    flags = (
        db.query(Flag)
        .filter(Flag.transaction_ref.in_(tx_ids))
        .order_by(Flag.created_at.desc())
        .all()
        if tx_ids
        else []
    )
    return CustomerHistoryOut(
        customer_ref=customer.id,
        pseudonymized_id=customer.pseudonymized_id,
        risk_profile=customer.risk_profile,
        transactions=transactions,
        flags=flags,
    )
