"""
Audit log (F8.1, F8.2). Local stand-in for S3 + Object Lock (compliance
mode) + CloudTrail data events — see infra/modules/audit.

Append-only is enforced two ways locally: the JSONL file is opened in
append-only mode and each line is hash-chained to the previous line's hash,
so any edit-in-place is detectable even though the local filesystem can't
give us S3 Object Lock's actual immutability guarantee. A SQLite index sits
alongside it purely for query performance (F8.5's "within minutes" bar) —
the JSONL file, not the index, is the source of truth.

F7.4 note: callers MUST NOT pass re-identified real values into `detail`.
This module does not scrub `detail` — the caller (core/reidentify.py) is
responsible for logging only actor/subject_id/job_id/justification, never
the resolved content.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.schemas import AuditEvent

_INDEX_DB = settings.data_dir / "audit_index.db"


@contextmanager
def _index_conn():
    conn = sqlite3.connect(_INDEX_DB)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_index() -> None:
    with _index_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_index (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                subject_id TEXT,
                job_id TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_subject ON audit_index (subject_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_job ON audit_index (job_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_index (timestamp)")


_init_index()


def _last_hash(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return "0" * 64
    with open(path, "rb") as f:
        last_line = b""
        for line in f:
            if line.strip():
                last_line = line
    if not last_line:
        return "0" * 64
    return json.loads(last_line)["_hash"]


def append_event(event: AuditEvent) -> None:
    path = settings.audit_log_path
    path.parent.mkdir(parents=True, exist_ok=True)

    record = event.model_dump(mode="json")
    prev_hash = _last_hash(path)
    chained = json.dumps(record, sort_keys=True) + prev_hash
    record["_prev_hash"] = prev_hash
    record["_hash"] = hashlib.sha256(chained.encode("utf-8")).hexdigest()

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    with _index_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO audit_index (event_id, event_type, actor, subject_id, job_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event.event_id, event.event_type, event.actor, event.subject_id, event.job_id,
             event.timestamp.isoformat()),
        )


def log_event(
    *, event_type: str, actor: str, subject_id: str | None = None, job_id: str | None = None,
    justification: str | None = None, detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_id=uuid.uuid4().hex, event_type=event_type, actor=actor,
        subject_id=subject_id, job_id=job_id, justification=justification,
        detail=detail or {}, timestamp=datetime.now(timezone.utc), region=settings.aws_region,
    )
    append_event(event)
    return event


def verify_chain_integrity() -> bool:
    """Recomputes the hash chain over the audit log; returns False if any
    line was altered or removed out of order."""
    path = settings.audit_log_path
    if not path.exists():
        return True
    prev_hash = "0" * 64
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            record = json.loads(line)
            claimed_hash, claimed_prev = record.pop("_hash"), record.pop("_prev_hash")
            if claimed_prev != prev_hash:
                return False
            recomputed = hashlib.sha256((json.dumps(record, sort_keys=True) + prev_hash).encode("utf-8")).hexdigest()
            if recomputed != claimed_hash:
                return False
            prev_hash = claimed_hash
    return True
