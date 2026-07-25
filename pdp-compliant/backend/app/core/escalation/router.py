"""
Escalation routing (F5). Decides whether a complaint stays on the local tier
or crosses into Zone C, and enforces the guarantees that make that crossing
safe.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.config import settings
from app.core.escalation import cost_ledger
from app.core.escalation.circuit_breaker import CircuitBreaker
from app.core.escalation.providers import EscalationError, EscalationProvider, get_provider
from app.core.pii import detect_all
from app.models.schemas import TriageOutput

logger = logging.getLogger("sentinel.escalation")

_breaker = CircuitBreaker()


class EscalationReason(str, Enum):
    LOW_CONFIDENCE = "low_confidence"
    LOCAL_UNAVAILABLE = "local_unavailable"
    SCHEMA_INVALID = "schema_invalid"
    MULTI_ISSUE = "multi_issue"


class EgressBlockedError(Exception):
    """F5.3: redundant pre-egress PII check found untokenized PII. This must
    never be caught and silently ignored — it means pseudonymization or the
    input guard upstream has a defect."""


class KillSwitchEngagedError(Exception):
    """F5.6: external egress is hard-disabled. Caller must route to local-only
    handling (or human review if local also failed)."""


def should_escalate(triage: TriageOutput | None, *, local_failed: bool) -> tuple[bool, EscalationReason | None]:
    if local_failed:
        return True, EscalationReason.LOCAL_UNAVAILABLE
    if triage is None:
        return True, EscalationReason.LOCAL_UNAVAILABLE
    if triage.multi_issue:
        return True, EscalationReason.MULTI_ISSUE
    if triage.overall_confidence < settings.escalation_confidence_threshold:
        return True, EscalationReason.LOW_CONFIDENCE
    return False, None


def _verify_no_untokenized_pii(tokenized_text: str) -> None:
    """F5.3: redundant check by design — pseudonymization already ran, but
    we re-verify immediately before anything leaves the jurisdiction."""
    detection = detect_all(tokenized_text)
    high_confidence_leaks = [e for e in detection.entities if e.confidence >= 0.7]
    if high_confidence_leaks:
        raise EgressBlockedError(
            f"pre-egress check found {len(high_confidence_leaks)} untokenized high-confidence "
            f"PII span(s); refusing to escalate job"
        )


@dataclass
class EscalationOutcome:
    triage: TriageOutput
    reason: EscalationReason
    provider: str
    cost_usd: float


def escalate(
    tokenized_text: str,
    *,
    job_id: str,
    reason: EscalationReason,
    provider_name: str | None = None,
    use_mock: bool = False,
) -> EscalationOutcome:
    if settings.escalation_kill_switch or not settings.escalation_enabled:
        raise KillSwitchEngagedError("external egress disabled (kill switch or escalation_enabled=false)")

    _verify_no_untokenized_pii(tokenized_text)

    if not _breaker.allow_request():
        raise EscalationError("escalation circuit breaker open; provider considered unavailable")

    provider: EscalationProvider = get_provider(provider_name or settings.escalation_provider, use_mock=use_mock)
    try:
        triage, usage = provider.classify(tokenized_text)
    except EscalationError:
        _breaker.record_failure()
        raise
    else:
        _breaker.record_success()

    cost_ledger.record(
        job_id=job_id, tier="escalation", provider=usage.provider,
        tokens_in=usage.tokens_in, tokens_out=usage.tokens_out,
        cost_usd=usage.estimated_cost_usd, reason=reason.value,
    )
    logger.info(
        "escalated job=%s reason=%s provider=%s tokens_in=%d tokens_out=%d cost_usd=%.6f",
        job_id, reason.value, usage.provider, usage.tokens_in, usage.tokens_out, usage.estimated_cost_usd,
    )
    return EscalationOutcome(triage=triage, reason=reason, provider=usage.provider, cost_usd=usage.estimated_cost_usd)
