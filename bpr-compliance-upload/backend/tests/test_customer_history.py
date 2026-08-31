import uuid
from datetime import datetime

from app.models import Customer, Flag, Transaction
from app.services.customers import get_customer_history


def _customer(db):
    c = Customer(pseudonymized_id=f"CUST-{uuid.uuid4().hex[:8]}")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_history_found_by_internal_id(db):
    cust = _customer(db)
    txn = Transaction(customer_ref=cust.id, amount=500.0, type="deposit", timestamp=datetime(2026, 8, 1), source_file="t")
    db.add(txn)
    db.commit()
    db.refresh(txn)
    db.add(Flag(transaction_ref=txn.id, rule_triggered="large_amount"))
    db.commit()

    history = get_customer_history(db, cust.id)
    assert history is not None
    assert len(history.transactions) == 1
    assert len(history.flags) == 1
    assert history.flags[0].transaction_ref == txn.id


def test_history_found_by_pseudonymized_id(db):
    cust = _customer(db)
    history = get_customer_history(db, cust.pseudonymized_id)
    assert history is not None
    assert history.customer_ref == cust.id
    assert history.transactions == []
    assert history.flags == []


def test_history_returns_none_for_unknown_ref(db):
    assert get_customer_history(db, "does-not-exist") is None
