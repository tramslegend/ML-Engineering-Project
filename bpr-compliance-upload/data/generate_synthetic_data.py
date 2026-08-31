"""Generates synthetic users, customers, and a sample legacy core-banking
CSV export (some rows deliberately malformed to exercise the FR-1..FR-3
quarantine path: missing fields, unknown customer id, garbled date format,
non-numeric amount).
"""
import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from faker import Faker

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Customer, Role, User

fake = Faker("id_ID")
random.seed(42)
Faker.seed(42)

TXN_TYPES = ["transfer_out", "transfer_in", "cash_deposit", "cash_withdrawal", "loan_disbursement", "loan_repayment"]


def seed_users(db):
    demo_users = [
        ("loan.officer@bpr.demo", "Budi Santoso", Role.loan_officer, "password123"),
        ("compliance.officer@bpr.demo", "Siti Rahayu", Role.compliance_officer, "password123"),
        ("auditor@bpr.demo", "Agus Wijaya", Role.auditor, "password123"),
    ]
    created = []
    for auth_id, name, role, pw in demo_users:
        existing = db.query(User).filter(User.auth_provider_id == auth_id).first()
        if existing:
            created.append(existing)
            continue
        user = User(name=name, role=role, auth_provider_id=auth_id, hashed_password=hash_password(pw))
        db.add(user)
        db.commit()
        db.refresh(user)
        created.append(user)
    return created


def seed_customers(db, n=15):
    customers = []
    for i in range(n):
        pseudo_id = f"CUST-{i:04d}"
        existing = db.query(Customer).filter(Customer.pseudonymized_id == pseudo_id).first()
        if existing:
            customers.append(existing)
            continue
        risk_profile = random.choices(["standard", "elevated", "high"], weights=[0.75, 0.18, 0.07])[0]
        customer = Customer(pseudonymized_id=pseudo_id, risk_profile=risk_profile)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        customers.append(customer)
    return customers


def generate_csv_export(customers, out_path: Path, n_good=60, n_bad=8):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base_time = datetime(2026, 8, 1)

    rows = [["pseudonymized_id", "amount", "type", "timestamp"]]

    for i in range(n_good):
        customer = random.choice(customers)
        # A handful of transactions deliberately large / frequent / deviant so
        # the screening rules (app/services/screening.py) actually trigger.
        if i % 11 == 0:
            amount = round(random.uniform(120_000_000, 300_000_000), 2)
        else:
            amount = round(random.uniform(50_000, 8_000_000), 2)
        txn_type = random.choice(TXN_TYPES)
        ts = base_time + timedelta(hours=random.randint(0, 24 * 25), minutes=random.randint(0, 59))
        # mixed date formats, as real legacy exports vary by branch
        fmt = random.choice(["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"])
        rows.append([customer.pseudonymized_id, str(amount), txn_type, ts.strftime(fmt)])

    # Deliberately malformed rows to exercise the quarantine path.
    bad_rows = [
        ["", "1000000", "transfer_out", "2026-08-05 10:00:00"],  # missing pseudonymized_id
        ["CUST-0001", "not_a_number", "transfer_out", "2026-08-05 10:00:00"],  # bad amount
        ["CUST-0002", "500000", "transfer_out", "31-13-2026"],  # unparseable date
        ["CUST-9999", "750000", "cash_deposit", "2026-08-06 11:00:00"],  # unknown customer
        ["CUST-0003", "250000", "", "2026-08-07 09:00:00"],  # missing type
        ["CUST-0004", "300000", "cash_withdrawal"],  # missing timestamp column entirely
        ["CUST-0005", "", "transfer_out", "2026-08-08 09:00:00"],  # missing amount
        ["CUST-0006", "1200000", "cash_deposit", "08/09/2026"],  # date-only, no time component -> matches none of DATE_FORMATS
    ]
    for row in bad_rows[:n_bad]:
        rows.append(row)

    random.shuffle(rows[1:])  # keep header first, shuffle data rows

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return out_path


def generate_no_header_csv(customers, out_path: Path, n=10):
    """A second sample export with NO header row at all — some BPR branch
    export tools omit it entirely (FR-2)."""
    base_time = datetime(2026, 8, 10)
    rows = []
    for i in range(n):
        customer = random.choice(customers)
        amount = round(random.uniform(50_000, 5_000_000), 2)
        txn_type = random.choice(TXN_TYPES)
        ts = base_time + timedelta(hours=random.randint(0, 48))
        rows.append([customer.pseudonymized_id, str(amount), txn_type, ts.strftime("%Y-%m-%d %H:%M:%S")])

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return out_path


if __name__ == "__main__":
    db = SessionLocal()
    try:
        users = seed_users(db)
        customers = seed_customers(db)
        print(f"Seeded {len(users)} users, {len(customers)} customers.")

        export_path = Path(__file__).resolve().parent / "sample_export.csv"
        generate_csv_export(customers, export_path)
        print(f"Wrote sample legacy export: {export_path}")

        no_header_path = Path(__file__).resolve().parent / "sample_export_no_header.csv"
        generate_no_header_csv(customers, no_header_path)
        print(f"Wrote no-header sample export: {no_header_path}")
    finally:
        db.close()
