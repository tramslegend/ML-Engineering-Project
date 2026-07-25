"""
Complaint record store. Local stand-in for the DynamoDB "Triage results"
table (§9, Zone B — tokenized content only; see F7.4 for why re-identified
text never lands here).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import settings
from app.models.schemas import ComplaintRecord


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.app_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_schema() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                record_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints (status)")


_init_schema()


def save(record: ComplaintRecord) -> None:
    record.updated_at = datetime.now(timezone.utc)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO complaints (job_id, status, record_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                status = excluded.status, record_json = excluded.record_json, updated_at = excluded.updated_at
            """,
            (record.job_id, record.status.value, record.model_dump_json(),
             record.created_at.isoformat(), record.updated_at.isoformat()),
        )


def get(job_id: str) -> ComplaintRecord | None:
    with _conn() as conn:
        row = conn.execute("SELECT record_json FROM complaints WHERE job_id = ?", (job_id,)).fetchone()
    return ComplaintRecord.model_validate_json(row["record_json"]) if row else None


def list_all(status: str | None = None, limit: int = 100) -> list[ComplaintRecord]:
    with _conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT record_json FROM complaints WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT record_json FROM complaints ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
    return [ComplaintRecord.model_validate_json(r["record_json"]) for r in rows]
