"""Cost ledger (§9 data model, F5.5, M6). Local stand-in for the DynamoDB
cost ledger table."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import settings


@contextmanager
def _conn():
    conn = sqlite3.connect(settings.cost_ledger_db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_schema() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cost_ledger (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                tier TEXT NOT NULL,
                provider TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


_init_schema()


def record(
    *, job_id: str, tier: str, provider: str, tokens_in: int, tokens_out: int,
    cost_usd: float, reason: str | None = None,
) -> None:
    """F5.5: log every escalation with reason, provider, token count, and cost."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO cost_ledger (id, job_id, tier, provider, tokens_in, tokens_out, cost_usd, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex, job_id, tier, provider, tokens_in, tokens_out,
                cost_usd, reason, datetime.now(timezone.utc).isoformat(),
            ),
        )


def total_cost(job_id: str | None = None) -> float:
    with _conn() as conn:
        if job_id:
            row = conn.execute("SELECT SUM(cost_usd) FROM cost_ledger WHERE job_id = ?", (job_id,)).fetchone()
        else:
            row = conn.execute("SELECT SUM(cost_usd) FROM cost_ledger").fetchone()
    return row[0] or 0.0
