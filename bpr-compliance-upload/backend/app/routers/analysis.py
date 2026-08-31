from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.analysis import run_analysis
from app.auth import require_roles
from app.db import get_db
from app.models import Role
from app.schemas import AnalysisRequest, AnalysisResponse
from app.services.audit import write_audit

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/query", response_model=AnalysisResponse)
def query_analysis(
    payload: AnalysisRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.compliance_officer, Role.auditor)),
):
    """Runs the LangGraph Compliance Analysis agent (LangChain SQL Agent +
    LangChain pandas/Python agent) against the read-only bpr_analyst_ro role.
    Every question is written to the audit log, same as any other
    agent-assisted compliance action."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    if not payload.thread_id.strip():
        raise HTTPException(status_code=400, detail="thread_id must not be empty")
    # Namespace by user id server-side so a client-supplied thread_id can never
    # be replayed to read or continue a different user's conversation, even
    # though thread ids are random UUIDs.
    scoped_thread_id = f"{user.id}:{payload.thread_id}"
    try:
        result = run_analysis(payload.question, scoped_thread_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    write_audit(db, actor=user.name, action="analysis_query_run", rationale=payload.question)
    return result
