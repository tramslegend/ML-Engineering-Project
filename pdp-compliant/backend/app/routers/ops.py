"""
Runtime-configurable operational controls (F5.2 threshold, F5.6 kill switch).

Real deployment: these values live in SSM Parameter Store per the Terraform
practice in §11 ("volatile configuration in SSM ... since user_data changes
force instance replacement"), read on each request or via a short-TTL cache.
Locally, `settings` is a process-wide singleton, so mutating it here is the
direct equivalent — no redeploy, takes effect on the next request.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_analyst
from app.config import settings
from app.core.escalation import cost_ledger

router = APIRouter(prefix="/api/ops", tags=["ops"])


@router.get("/config")
def get_config(_actor: str = Depends(require_analyst)) -> dict:
    return {
        "escalation_confidence_threshold": settings.escalation_confidence_threshold,
        "escalation_enabled": settings.escalation_enabled,
        "escalation_kill_switch": settings.escalation_kill_switch,
        "detection_confidence_floor": settings.detection_confidence_floor,
        "injection_block_threshold": settings.injection_block_threshold,
    }


class ThresholdUpdate(BaseModel):
    escalation_confidence_threshold: float = Field(ge=0.0, le=1.0)


@router.post("/config/escalation-threshold")
def set_escalation_threshold(payload: ThresholdUpdate, _actor: str = Depends(require_analyst)) -> dict:
    """F5.2."""
    settings.escalation_confidence_threshold = payload.escalation_confidence_threshold
    return {"escalation_confidence_threshold": settings.escalation_confidence_threshold}


class KillSwitchUpdate(BaseModel):
    engaged: bool


@router.post("/config/kill-switch")
def set_kill_switch(payload: KillSwitchUpdate, _actor: str = Depends(require_analyst)) -> dict:
    """F5.6: hard kill switch disabling all external egress, degrading to local-only."""
    settings.escalation_kill_switch = payload.engaged
    return {"escalation_kill_switch": settings.escalation_kill_switch}


@router.get("/cost")
def get_cost(job_id: str | None = None, _actor: str = Depends(require_analyst)) -> dict:
    """M6: cost per complaint, documented, all tiers."""
    return {"job_id": job_id, "total_cost_usd": cost_ledger.total_cost(job_id)}
