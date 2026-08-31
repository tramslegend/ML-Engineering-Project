"""CSV ingestion for simulated legacy core-banking exports (FR-1..FR-3).

Real legacy exports from BPR core banking systems are inconsistent: some
batches have a header row, some don't; date formats vary by branch/export
tool. This module normalizes what it can and quarantines what it can't,
rather than silently dropping rows or crashing the whole batch on one bad
line.
"""
import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Customer, Transaction

EXPECTED_COLUMNS = ["pseudonymized_id", "amount", "type", "timestamp"]

# Legacy exports have been observed with any of these date formats depending
# on branch/export tool version.
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y",
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%d",
]


@dataclass
class IngestionReport:
    source_file: str
    total_rows: int = 0
    inserted: int = 0
    quarantined: int = 0
    quarantine_file: str | None = None
    errors: list[dict] = field(default_factory=list)


def _parse_timestamp(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {raw!r}")


def _looks_like_header(row: list[str]) -> bool:
    normalized = [c.strip().lower() for c in row]
    return "pseudonymized_id" in normalized or "amount" in normalized


def _row_to_dict(row: list[str], header: list[str] | None) -> dict:
    if header:
        return dict(zip(header, row))
    # No header row present in this batch: fall back to the canonical
    # column order rather than dropping the whole file (FR-2).
    return dict(zip(EXPECTED_COLUMNS, row))


def ingest_csv(db: Session, file_path: str) -> IngestionReport:
    source_name = Path(file_path).name
    report = IngestionReport(source_file=source_name)

    quarantine_dir = Path(settings.quarantine_dir)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_path = quarantine_dir / f"{source_name}.quarantine.jsonl"
    quarantined_rows: list[dict] = []

    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        report.quarantine_file = None
        return report

    header: list[str] | None = None
    data_rows = rows
    if _looks_like_header(rows[0]):
        header = [c.strip().lower() for c in rows[0]]
        data_rows = rows[1:]

    for i, raw_row in enumerate(data_rows):
        line_no = i + (2 if header else 1)
        report.total_rows += 1

        if not raw_row or all(not c.strip() for c in raw_row):
            continue  # skip genuinely blank lines, not a data-quality error

        record = _row_to_dict(raw_row, header)
        error = None
        try:
            missing = [c for c in EXPECTED_COLUMNS if not record.get(c, "").strip()]
            if missing:
                raise ValueError(f"Missing required field(s): {missing}")

            pseudo_id = record["pseudonymized_id"].strip()
            amount = float(record["amount"])
            txn_type = record["type"].strip()
            timestamp = _parse_timestamp(record["timestamp"])

            customer = db.query(Customer).filter(Customer.pseudonymized_id == pseudo_id).first()
            if customer is None:
                raise ValueError(f"Unknown customer pseudonymized_id: {pseudo_id!r}")

            txn = Transaction(
                customer_ref=customer.id,
                amount=amount,
                type=txn_type,
                timestamp=timestamp,
                source_file=source_name,
            )
            db.add(txn)
            db.commit()
            report.inserted += 1
        except Exception as exc:  # noqa: BLE001 - intentionally broad: any row-level failure is quarantined, not fatal
            db.rollback()
            error = str(exc)
            report.quarantined += 1
            report.errors.append({"line": line_no, "row": raw_row, "error": error})
            quarantined_rows.append({"line": line_no, "row": raw_row, "error": error})

    if quarantined_rows:
        with open(quarantine_path, "w", encoding="utf-8") as qf:
            for entry in quarantined_rows:
                qf.write(json.dumps(entry) + "\n")
        report.quarantine_file = str(quarantine_path)

    return report
