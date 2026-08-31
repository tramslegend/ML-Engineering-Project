import csv
import uuid
from pathlib import Path

from app.models import Customer
from app.services.ingestion import ingest_csv


def _make_customer(db, pseudo_id: str) -> Customer:
    customer = Customer(pseudonymized_id=pseudo_id)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_ingest_valid_rows_inserted(db, tmp_path):
    cust = _make_customer(db, f"TEST-{uuid.uuid4().hex[:8]}")
    csv_path: Path = tmp_path / "good.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pseudonymized_id", "amount", "type", "timestamp"])
        w.writerow([cust.pseudonymized_id, "150000", "cash_deposit", "2026-08-01 10:00:00"])

    report = ingest_csv(db, str(csv_path))
    assert report.inserted == 1
    assert report.quarantined == 0


def test_ingest_missing_field_quarantined(db, tmp_path):
    cust = _make_customer(db, f"TEST-{uuid.uuid4().hex[:8]}")
    csv_path: Path = tmp_path / "bad.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pseudonymized_id", "amount", "type", "timestamp"])
        w.writerow([cust.pseudonymized_id, "", "cash_deposit", "2026-08-01 10:00:00"])

    report = ingest_csv(db, str(csv_path))
    assert report.inserted == 0
    assert report.quarantined == 1
    assert report.quarantine_file is not None
    assert Path(report.quarantine_file).exists()


def test_ingest_unknown_customer_quarantined(db, tmp_path):
    csv_path: Path = tmp_path / "unknown.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pseudonymized_id", "amount", "type", "timestamp"])
        w.writerow(["NO-SUCH-CUSTOMER-XYZ", "150000", "cash_deposit", "2026-08-01 10:00:00"])

    report = ingest_csv(db, str(csv_path))
    assert report.quarantined == 1
    assert "Unknown customer" in report.errors[0]["error"]


def test_ingest_mixed_date_formats_all_parse(db, tmp_path):
    cust = _make_customer(db, f"TEST-{uuid.uuid4().hex[:8]}")
    csv_path: Path = tmp_path / "dates.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pseudonymized_id", "amount", "type", "timestamp"])
        w.writerow([cust.pseudonymized_id, "1000", "cash_deposit", "2026-08-01 10:00:00"])
        w.writerow([cust.pseudonymized_id, "1000", "cash_deposit", "01/08/2026 10:00"])
        w.writerow([cust.pseudonymized_id, "1000", "cash_deposit", "2026-08-01T10:00:00"])

    report = ingest_csv(db, str(csv_path))
    assert report.inserted == 3
    assert report.quarantined == 0


def test_ingest_no_header_uses_fallback_column_order(db, tmp_path):
    cust = _make_customer(db, f"TEST-{uuid.uuid4().hex[:8]}")
    csv_path: Path = tmp_path / "noheader.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([cust.pseudonymized_id, "1000", "cash_deposit", "2026-08-01 10:00:00"])

    report = ingest_csv(db, str(csv_path))
    assert report.inserted == 1
