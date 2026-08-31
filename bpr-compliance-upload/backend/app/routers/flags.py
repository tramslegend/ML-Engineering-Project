from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.models import Flag, FlagStatus, Role, Transaction
from app.schemas import FlagDecisionRequest, FlagOut
from app.services.audit import write_audit
from app.services.screening import screen_unflagged_transactions

router = APIRouter(prefix="/flags", tags=["flags"])


@router.post("/screen", response_model=list[FlagOut])
def trigger_screening(
    db: Session = Depends(get_db),
    _user=Depends(require_roles(Role.compliance_officer)),
):
    """FR-4/5/6: rule-screens every un-flagged transaction and, for each hit,
    runs the LangGraph screening + reviewer agents to attach a rationale."""
    return screen_unflagged_transactions(db)

_DECISION_TO_STATUS = {
    "accepted": FlagStatus.accepted,
    "rejected": FlagStatus.rejected,
    "escalated": FlagStatus.escalated,
}


@router.get("", response_model=list[FlagOut])
def list_flags(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(Role.compliance_officer, Role.auditor)),
):
    query = db.query(Flag)
    if status_filter:
        query = query.filter(Flag.status == FlagStatus(status_filter))
    return query.order_by(Flag.created_at.desc()).all()


@router.post("/{flag_id}/decision", response_model=FlagOut)
def decide_flag(
    flag_id: str,
    payload: FlagDecisionRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.compliance_officer)),
):
    if payload.decision not in _DECISION_TO_STATUS:
        raise HTTPException(status_code=400, detail=f"decision must be one of {list(_DECISION_TO_STATUS)}")

    flag = db.query(Flag).filter(Flag.id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")

    flag.status = _DECISION_TO_STATUS[payload.decision]
    flag.decided_by = user.id
    flag.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(flag)

    # FR-7: the decision is logged with timestamp and user ID.
    write_audit(
        db,
        actor=user.name,
        action=f"flag_{payload.decision}",
        entity_ref=flag.id,
        rationale=payload.note,
    )
    return flag
