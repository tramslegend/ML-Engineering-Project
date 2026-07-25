"""F8: audit and compliance reporting endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_analyst, require_reidentify_permission
from app.core.audit import reports
from app.core.audit.log import verify_chain_integrity
from app.core.erasure import erase_subject

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


@router.get("/residency-report")
def residency_report(start: datetime, end: datetime, _actor: str = Depends(require_analyst)) -> dict:
    """F8.3."""
    return reports.residency_report(start, end)


@router.get("/subject-access/{subject_id}")
def subject_access_report(subject_id: str, _actor: str = Depends(require_analyst)) -> dict:
    """F8.4."""
    return reports.per_subject_access_report(subject_id)


@router.get("/incident-scope")
def incident_scope(start: datetime, end: datetime, _actor: str = Depends(require_analyst)) -> dict:
    """F8.5."""
    return reports.incident_scope_query(start, end)


@router.get("/audit-trail/{job_id}")
def audit_trail(job_id: str, _actor: str = Depends(require_analyst)) -> dict:
    """F10.5."""
    return reports.job_audit_trail(job_id)


@router.get("/audit-integrity")
def audit_integrity(_actor: str = Depends(require_analyst)) -> dict:
    """Evidence-pack helper: proves the local hash-chain hasn't been tampered
    with. Real deployment relies on S3 Object Lock instead of this check."""
    return {"intact": verify_chain_integrity()}


class ErasureRequest(BaseModel):
    justification: str


@router.post("/erase/{subject_id}")
def erase(subject_id: str, payload: ErasureRequest, actor: str = Depends(require_reidentify_permission)) -> dict:
    """F3.6/N19: erasure demonstration. Gated behind the re-identify
    permission since erasure and re-identification both require Zone A
    access to subject-linked data."""
    if not payload.justification.strip():
        raise HTTPException(status_code=400, detail="justification is required")
    count = erase_subject(subject_id, actor=actor, justification=payload.justification)
    return {"subject_id": subject_id, "tokens_orphaned": count}
