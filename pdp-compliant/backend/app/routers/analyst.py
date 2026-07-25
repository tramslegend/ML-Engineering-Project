"""F10: analyst interface API. F9.2/F9.3 decision capture."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.auth import require_analyst
from app.core.review_queue import queue as review_queue
from app.models.schemas import ComplaintStatus, ReviewSubmission

router = APIRouter(prefix="/api/complaints", tags=["analyst"])

_TOKEN_RE = re.compile(r"\[([A-Z_]+)_(\d+)\]")


@router.get("")
def list_complaints(status: str | None = None, _actor: str = Depends(require_analyst)) -> list[dict]:
    """F10.1: list view with severity, category, age."""
    records = db.list_all(status=status)
    now = datetime.now(timezone.utc)
    out = []
    for r in records:
        age_s = (now - r.created_at).total_seconds()
        out.append({
            "job_id": r.job_id,
            "status": r.status.value,
            "category": r.triage.category if r.triage else None,
            "severity": r.triage.severity.value if r.triage else None,
            "age_seconds": age_s,
            "guardrail_flags": r.guardrail_flags,
        })
    return out


@router.get("/{job_id}")
def get_complaint(job_id: str, _actor: str = Depends(require_analyst)) -> dict:
    """F10.2/F10.3: detail view. Content is tokenized by default — the UI
    marks which fields are tokens so the analyst knows what re-identification
    would reveal, without resolving anything until F7's endpoint is called."""
    record = db.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")

    tokens_present = sorted(set(m.group(0) for m in _TOKEN_RE.finditer(record.tokenized_text or "")))
    return {
        "job_id": record.job_id,
        "status": record.status.value,
        "subject_id": record.subject_id,
        "tokenized_text": record.tokenized_text,
        "tokens_present": tokens_present,
        "triage": record.triage.model_dump() if record.triage else None,
        "escalation_reason": record.escalation_reason,
        "guardrail_flags": record.guardrail_flags,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.post("/{job_id}/review")
def submit_review(job_id: str, submission: ReviewSubmission, _actor: str = Depends(require_analyst)) -> dict:
    """F10.4: one-click accept, inline edit, structured reject."""
    record = db.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")

    review_queue.record_decision(job_id, submission)

    status_map = {
        "accept": ComplaintStatus.REVIEWED_ACCEPTED,
        "edit": ComplaintStatus.REVIEWED_EDITED,
        "reject": ComplaintStatus.REVIEWED_REJECTED,
    }
    record.status = status_map[submission.decision.value]
    if submission.decision.value == "edit" and submission.edited_output:
        record.triage = submission.edited_output
    db.save(record)
    return {"job_id": job_id, "status": record.status.value}
