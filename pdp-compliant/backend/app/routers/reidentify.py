"""F7: re-identification endpoint. Zone A only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app import db
from app.auth import require_reidentify_permission
from app.core.reidentify import reidentify
from app.models.schemas import ReidentifyRequest, ReidentifyResponse

router = APIRouter(prefix="/api/complaints", tags=["reidentify"])


@router.post("/{job_id}/reidentify", response_model=ReidentifyResponse)
def reidentify_complaint(
    job_id: str,
    payload: ReidentifyRequest,
    actor: str = Depends(require_reidentify_permission),
) -> ReidentifyResponse:
    if payload.job_id != job_id:
        raise HTTPException(status_code=400, detail="job_id in path and body must match")

    record = db.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    if record.subject_id is None or record.tokenized_text is None:
        raise HTTPException(status_code=409, detail="job has not been tokenized yet")
    if not payload.justification.strip():
        raise HTTPException(status_code=400, detail="justification is required (F7.3)")

    text, resolved = reidentify(
        record.tokenized_text,
        subject_id=record.subject_id,
        job_id=job_id,
        actor=actor,
        justification=payload.justification,
        fields=payload.fields,
    )
    # F7.4: the resolved text is returned to the caller only — it must never
    # be persisted to `db`, logged, or otherwise land outside this response.
    return ReidentifyResponse(job_id=job_id, reidentified_text=text, fields_resolved=resolved)
