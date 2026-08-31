from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.models import Role, Transaction
from app.schemas import TransactionOut

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    limit: int = 100,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(Role.compliance_officer, Role.auditor)),
):
    return db.query(Transaction).order_by(Transaction.timestamp.desc()).limit(limit).all()
