"""Compliance reporting (F8.3-F8.5), read from the audit index."""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime

from app.config import settings
from app.core.audit.log import _INDEX_DB  # noqa: F401 - re-exported path for callers/tests


def _rows(query: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(settings.data_dir / "audit_index.db")
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
    finally:
        conn.close()


def residency_report(start: datetime, end: datetime) -> dict:
    """F8.3: per time period, what processing occurred where, and what left
    the jurisdiction. Any event_type prefixed 'escalation.' is the only
    category that leaves ap-southeast-3 (Zone C egress, §6.1)."""
    rows = _rows(
        "SELECT event_type, timestamp FROM audit_index WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
        (start.isoformat(), end.isoformat()),
    )
    by_type = Counter(r["event_type"] for r in rows)
    left_jurisdiction = sum(v for k, v in by_type.items() if k.startswith("escalation."))
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "region": settings.aws_region,
        "total_events": len(rows),
        "events_by_type": dict(by_type),
        "events_leaving_jurisdiction": left_jurisdiction,
    }


def per_subject_access_report(subject_id: str) -> dict:
    """F8.4: supports a data subject access request — every audit event
    touching this subject_id, in order."""
    rows = _rows(
        "SELECT event_id, event_type, actor, job_id, timestamp FROM audit_index "
        "WHERE subject_id = ? ORDER BY timestamp",
        (subject_id,),
    )
    return {"subject_id": subject_id, "event_count": len(rows), "events": rows}


def job_audit_trail(job_id: str) -> dict:
    """F10.5: read-only compliance view for a single analyst-facing item."""
    rows = _rows(
        "SELECT event_id, event_type, actor, subject_id, timestamp FROM audit_index "
        "WHERE job_id = ? ORDER BY timestamp",
        (job_id,),
    )
    return {"job_id": job_id, "event_count": len(rows), "events": rows}


def incident_scope_query(start: datetime, end: datetime) -> dict:
    """F8.5: 'which subjects were affected between T1 and T2' — must return
    within minutes to serve the 3x24 hour breach notification window (§2)."""
    rows = _rows(
        "SELECT DISTINCT subject_id FROM audit_index "
        "WHERE timestamp BETWEEN ? AND ? AND subject_id IS NOT NULL",
        (start.isoformat(), end.isoformat()),
    )
    subjects = [r["subject_id"] for r in rows]
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "affected_subject_count": len(subjects),
        "affected_subjects": subjects,
    }
