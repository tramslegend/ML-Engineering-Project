from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.models import ReportDraft, ReportStatus, Role
from app.schemas import ReportDraftOut, ReportDraftRequest
from app.services.audit import write_audit
from app.services.reporting import generate_report_draft

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/draft", response_model=ReportDraftOut)
async def draft_report(
    payload: ReportDraftRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.compliance_officer)),
):
    draft = await generate_report_draft(db, payload.period, generated_by=user.name)
    write_audit(db, actor=user.name, action="report_draft_generated", entity_ref=draft.id)
    return draft


@router.post("/{report_id}/approve", response_model=ReportDraftOut)
def approve_report(
    report_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.compliance_officer)),
):
    from datetime import datetime

    draft = db.query(ReportDraft).filter(ReportDraft.id == report_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Report draft not found")

    # FR-10: no draft is auto-finalized without explicit compliance officer sign-off.
    draft.status = ReportStatus.approved
    draft.approved_by = user.id
    draft.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(draft)

    write_audit(db, actor=user.name, action="report_approved", entity_ref=draft.id)
    return draft
