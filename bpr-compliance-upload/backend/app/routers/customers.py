from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.models import Role
from app.schemas import CustomerHistoryOut
from app.services.customers import get_customer_history

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/{customer_ref}/history", response_model=CustomerHistoryOut)
def customer_history(
    customer_ref: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(Role.loan_officer, Role.compliance_officer, Role.auditor)),
):
    history = get_customer_history(db, customer_ref)
    if not history:
        raise HTTPException(status_code=404, detail="Customer not found")
    return history
