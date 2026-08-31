from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.models import AuditLog, Role
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    actor: str | None = None,
    action: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(Role.auditor)),
):
    query = db.query(AuditLog)
    if actor:
        query = query.filter(AuditLog.actor == actor)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
