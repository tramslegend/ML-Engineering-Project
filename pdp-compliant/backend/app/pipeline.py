"""
Processing pipeline (§6.2). Orchestrates ingest -> detect -> pseudonymize ->
guard(input) -> infer(local) -> route -> guard(output) -> [reidentify happens
separately, on-demand, per F7.1] -> review.

Runs as a FastAPI BackgroundTask locally, which is the scaffold's stand-in
for SQS + Step Functions (§11) — the function boundaries here map directly
onto the state-machine states a real Step Functions definition would encode,
so lifting this into Step Functions later is a translation, not a redesign.
"""
from __future__ import annotations

import logging
import uuid

from app import db
from app.config import settings
from app.core.audit.log import log_event
from app.core.escalation.router import (
    EgressBlockedError,
    EscalationReason,
    KillSwitchEngagedError,
    escalate,
    should_escalate,
)
from app.core.escalation.providers import EscalationError
from app.core.guardrails.input_guard import check_input
from app.core.guardrails.output_guard import check_output
from app.core.inference.client import LocalInferenceUnavailable, get_local_inference_client
from app.core.pii import DetectionFailedError, detect_all
from app.core.review_queue import queue as review_queue
from app.core.vault.pseudonymize import pseudonymize
from app.models.schemas import ComplaintRecord, ComplaintStatus

logger = logging.getLogger("sentinel.pipeline")


def new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:16]}"


def ingest(job_id: str, raw_text: str) -> ComplaintRecord:
    """F1.1-F1.5."""
    if len(raw_text.encode("utf-8")) > settings.max_upload_bytes:
        raise ValueError(f"input exceeds max size of {settings.max_upload_bytes} bytes")

    raw_path = settings.raw_docs_dir / f"{job_id}.txt"
    raw_path.write_text(raw_text, encoding="utf-8")  # dev stand-in for SSE-KMS S3 write (F1.3)

    record = ComplaintRecord(job_id=job_id, status=ComplaintStatus.INGESTED)
    db.save(record)
    log_event(event_type="ingest.received", actor="system", job_id=job_id,
              detail={"size_bytes": len(raw_text.encode("utf-8"))})
    return record


def run_pipeline(job_id: str, raw_text: str) -> None:
    """Runs steps 2-10 of §6.2. Any early return leaves the record in the
    status it was last saved at, and — if applicable — enqueued in the
    review queue with the reason a human needs to see."""
    record = db.get(job_id)
    if record is None:
        logger.error("run_pipeline called for unknown job_id=%s", job_id)
        return

    # --- 2. Detect ---
    record.status = ComplaintStatus.DETECTING
    db.save(record)
    try:
        detection = detect_all(raw_text)
    except DetectionFailedError as exc:
        record.status = ComplaintStatus.DETECTION_FAILED_CLOSED
        db.save(record)
        log_event(event_type="detect.failed_closed", actor="system", job_id=job_id, detail={"error": str(exc)})
        return

    record.detection = detection
    if detection.below_floor:
        record.status = ComplaintStatus.PENDING_DETECTION_REVIEW
        db.save(record)
        review_queue.enqueue(job_id, reason="detection_uncertain")
        log_event(event_type="detect.below_confidence_floor", actor="system", job_id=job_id,
                  detail={"min_confidence": detection.min_confidence})
        return

    log_event(event_type="detect.completed", actor="system", job_id=job_id,
              detail={"entity_count": len(detection.entities), "min_confidence": detection.min_confidence})

    # --- 3. Pseudonymize ---
    pseudo = pseudonymize(raw_text, detection, job_id=job_id)
    record.subject_id = pseudo.subject_id
    record.tokenized_text = pseudo.tokenized_text
    record.status = ComplaintStatus.TOKENIZED
    db.save(record)
    tokenized_path = settings.tokenized_docs_dir / f"{job_id}.txt"
    tokenized_path.write_text(pseudo.tokenized_text, encoding="utf-8")
    log_event(event_type="pseudonymize.completed", actor="system", job_id=job_id,
              subject_id=pseudo.subject_id, detail={"token_count": len(pseudo.tokens)})

    # --- 4. Guard (input) ---
    input_guard_result = check_input(pseudo.tokenized_text)
    record.guardrail_flags.extend(input_guard_result.flags)
    if input_guard_result.blocked:
        record.status = ComplaintStatus.INPUT_BLOCKED
        db.save(record)
        review_queue.enqueue(job_id, reason="guardrail")
        log_event(event_type="guard.input_blocked", actor="system", job_id=job_id,
                  subject_id=pseudo.subject_id, detail={"rules": input_guard_result.triggered_rules})
        return
    if input_guard_result.abuse_detected:
        review_queue.enqueue(job_id, reason="guardrail")  # F6.2: priority human routing
        log_event(event_type="guard.abuse_flagged", actor="system", job_id=job_id, subject_id=pseudo.subject_id)

    # --- 5. Infer (local) + 6. Route ---
    local_client = get_local_inference_client(use_mock=settings.use_mock_local_inference)
    triage = None
    local_failed = False
    try:
        triage = local_client.classify(pseudo.tokenized_text)
        record.triage = triage
        record.status = ComplaintStatus.LOCAL_INFERRED
        db.save(record)
        log_event(event_type="infer.local_completed", actor="system", job_id=job_id,
                  subject_id=pseudo.subject_id, detail={"confidence": triage.overall_confidence})
    except LocalInferenceUnavailable as exc:
        local_failed = True
        log_event(event_type="infer.local_unavailable", actor="system", job_id=job_id,
                  subject_id=pseudo.subject_id, detail={"error": str(exc)})

    escalate_needed, reason = should_escalate(triage, local_failed=local_failed)
    if escalate_needed:
        try:
            outcome = escalate(
                pseudo.tokenized_text, job_id=job_id,
                reason=reason or EscalationReason.LOCAL_UNAVAILABLE,
                use_mock=settings.use_mock_escalation,
            )
            triage = outcome.triage
            record.triage = triage
            record.status = ComplaintStatus.ESCALATED
            record.escalation_reason = outcome.reason.value
            db.save(record)
            log_event(event_type="escalation.completed", actor="system", job_id=job_id,
                      subject_id=pseudo.subject_id,
                      detail={"reason": outcome.reason.value, "provider": outcome.provider, "cost_usd": outcome.cost_usd})
        except (EgressBlockedError, KillSwitchEngagedError, EscalationError) as exc:
            log_event(event_type="escalation.failed", actor="system", job_id=job_id,
                      subject_id=pseudo.subject_id, detail={"error": str(exc)})
            if triage is None:
                record.status = ComplaintStatus.PENDING_REVIEW
                db.save(record)
                review_queue.enqueue(job_id, reason="escalation_unavailable")
                return
            # local result exists but was below threshold; surface it with the
            # low-confidence flag rather than losing the work.
            review_queue.enqueue(job_id, reason="low_confidence")

    if triage is None:
        record.status = ComplaintStatus.PENDING_REVIEW
        db.save(record)
        review_queue.enqueue(job_id, reason="local_unavailable")
        return

    # --- 7. Guard (output) ---
    output_guard_result = check_output(triage)
    record.guardrail_flags.extend(output_guard_result.flags)
    if output_guard_result.blocked:
        record.status = ComplaintStatus.OUTPUT_BLOCKED
        db.save(record)
        review_queue.enqueue(job_id, reason="guardrail")
        log_event(event_type="guard.output_blocked", actor="system", job_id=job_id,
                  subject_id=pseudo.subject_id, detail={"rules": output_guard_result.triggered_rules})
        return

    # --- 8/9. Ready for analyst review (NG4: humans decide, always) ---
    record.status = ComplaintStatus.PENDING_REVIEW
    db.save(record)
    if triage.overall_confidence < settings.escalation_confidence_threshold:
        review_queue.enqueue(job_id, reason="low_confidence")
    log_event(event_type="pipeline.ready_for_review", actor="system", job_id=job_id, subject_id=pseudo.subject_id)
