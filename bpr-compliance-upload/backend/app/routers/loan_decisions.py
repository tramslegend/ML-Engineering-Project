from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session

from app.auth import require_roles
from app.db import get_db
from app.models import LoanDecision, Role
from app.schemas import LoanDecisionCreate, LoanDecisionOut
from app.services.audit import write_audit

router = APIRouter(prefix="/loan-decisions", tags=["loan-decisions"])


@router.get("", response_model=list[LoanDecisionOut])
def list_loan_decisions(
    customer_ref: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user=Depends(require_roles(Role.loan_officer, Role.compliance_officer, Role.auditor)),
):
    query = db.query(LoanDecision)
    if customer_ref:
        query = query.filter(LoanDecision.customer_ref == customer_ref)
    return query.order_by(LoanDecision.timestamp.desc()).limit(limit).all()


@router.post("", response_model=LoanDecisionOut)
def create_loan_decision(
    payload: LoanDecisionCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.loan_officer)),
):
    decision = LoanDecision(
        customer_ref=payload.customer_ref,
        committee_notes=payload.committee_notes,
        decision=payload.decision,
        decided_by=user.id,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    write_audit(
        db,
        actor=user.name,
        action="loan_decision_logged",
        entity_ref=decision.id,
        rationale=payload.committee_notes,
    )
    return decision
