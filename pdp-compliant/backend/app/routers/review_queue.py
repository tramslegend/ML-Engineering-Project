"""F9.4: queue depth and age exposed as metrics."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import require_analyst
from app.core.review_queue import queue as review_queue

router = APIRouter(prefix="/api/review-queue", tags=["review-queue"])


@router.get("")
def get_review_queue(_actor: str = Depends(require_analyst)) -> dict:
    items = review_queue.list_queue()
    now = datetime.now(timezone.utc)
    ages = [(now - item.enqueued_at).total_seconds() for item in items]
    return {
        "depth": len(items),
        "oldest_age_seconds": max(ages) if ages else 0,
        "items": [
            {"job_id": i.job_id, "reason": i.reason, "enqueued_at": i.enqueued_at.isoformat()}
            for i in items
        ],
    }
