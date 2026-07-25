"""F1: ingestion endpoint."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.auth import require_analyst
from app.models.schemas import ComplaintRecord
from app.pipeline import ingest, new_job_id, run_pipeline
from pydantic import BaseModel

router = APIRouter(prefix="/api/complaints", tags=["ingestion"])


class IngestRequest(BaseModel):
    text: str


class IngestResponse(BaseModel):
    job_id: str
    status: str


@router.post("", response_model=IngestResponse, status_code=202)
def ingest_complaint(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    _actor: str = Depends(require_analyst),
) -> IngestResponse:
    """F1.2: returns a job ID immediately; processing runs in the background."""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    job_id = new_job_id()
    try:
        record: ComplaintRecord = ingest(job_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    background_tasks.add_task(run_pipeline, job_id, payload.text)
    return IngestResponse(job_id=record.job_id, status=record.status.value)
