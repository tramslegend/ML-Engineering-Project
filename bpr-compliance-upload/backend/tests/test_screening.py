import uuid
from datetime import datetime

from app.models import Customer, Transaction
from app.services.screening import (
    DEVIATION_MULTIPLIER,
    FREQUENCY_COUNT_THRESHOLD,
    LARGE_AMOUNT_THRESHOLD,
    screen_transaction,
)


def _customer(db):
    c = Customer(pseudonymized_id=f"SCR-{uuid.uuid4().hex[:8]}")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_large_amount_rule_triggers(db):
    cust = _customer(db)
    txn = Transaction(customer_ref=cust.id, amount=LARGE_AMOUNT_THRESHOLD + 1, type="transfer_out", timestamp=datetime(2026, 8, 1), source_file="t")
    db.add(txn)
    db.commit()
    db.refresh(txn)

    results = screen_transaction(db, txn)
    triggered = {r.rule_triggered for r in results}
    assert "large_amount" in triggered


def test_small_amount_no_trigger(db):
    cust = _customer(db)
    txn = Transaction(customer_ref=cust.id, amount=1000.0, type="transfer_out", timestamp=datetime(2026, 8, 1), source_file="t")
    db.add(txn)
    db.commit()
    db.refresh(txn)

    results = screen_transaction(db, txn)
    assert results == []


def test_frequency_rule_triggers(db):
    cust = _customer(db)
    for i in range(FREQUENCY_COUNT_THRESHOLD + 2):
        db.add(Transaction(customer_ref=cust.id, amount=1000.0, type="transfer_out", timestamp=datetime(2026, 8, 1, 10, i), source_file="t"))
    db.commit()

    last_txn = db.query(Transaction).filter(Transaction.customer_ref == cust.id).order_by(Transaction.timestamp.desc()).first()
    results = screen_transaction(db, last_txn)
    triggered = {r.rule_triggered for r in results}
    assert "high_frequency" in triggered


def test_profile_deviation_rule_triggers(db):
    cust = _customer(db)
    for i in range(5):
        db.add(Transaction(customer_ref=cust.id, amount=100_000.0, type="transfer_out", timestamp=datetime(2026, 7, 1, 10, i), source_file="t"))
    db.commit()

    outlier = Transaction(customer_ref=cust.id, amount=100_000.0 * DEVIATION_MULTIPLIER + 1, type="transfer_out", timestamp=datetime(2026, 8, 1), source_file="t")
    db.add(outlier)
    db.commit()
    db.refresh(outlier)

    results = screen_transaction(db, outlier)
    triggered = {r.rule_triggered for r in results}
    assert "profile_deviation" in triggered
