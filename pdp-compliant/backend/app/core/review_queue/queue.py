"""Human review queue (F9)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import settings
from app.models.schemas import ReviewItem, ReviewSubmission


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
            CREATE TABLE IF NOT EXISTS review_queue (
                job_id TEXT PRIMARY KEY,
                reason TEXT NOT NULL,
                enqueued_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_decisions (
                job_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                analyst_id TEXT NOT NULL,
                edited_output_json TEXT,
                justification TEXT,
                decided_at TEXT NOT NULL
            )
            """
        )


_init_schema()


def enqueue(job_id: str, reason: str) -> None:
    """F9.1. Idempotent: re-enqueuing an item already in the queue is a no-op."""
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO review_queue (job_id, reason, enqueued_at) VALUES (?, ?, ?)",
            (job_id, reason, datetime.now(timezone.utc).isoformat()),
        )


def dequeue(job_id: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM review_queue WHERE job_id = ?", (job_id,))


def list_queue(limit: int = 100) -> list[ReviewItem]:
    """F9.4: queue depth/age are derivable from this list (len(), and
    now - enqueued_at per item) — exposed as metrics by the router layer."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT job_id, reason, enqueued_at FROM review_queue ORDER BY enqueued_at ASC LIMIT ?", (limit,)
        ).fetchall()
    return [ReviewItem(job_id=r["job_id"], reason=r["reason"], enqueued_at=r["enqueued_at"]) for r in rows]


def queue_depth() -> int:
    with _conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM review_queue").fetchone()[0]


def record_decision(job_id: str, submission: ReviewSubmission) -> None:
    """F9.2/F9.3: capture the analyst's decision as labelled data for
    evaluation, then remove the item from the open queue."""
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO review_decisions (job_id, decision, analyst_id, edited_output_json, justification, decided_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, submission.decision.value, submission.analyst_id,
                submission.edited_output.model_dump_json() if submission.edited_output else None,
                submission.justification, datetime.now(timezone.utc).isoformat(),
            ),
        )
    dequeue(job_id)
