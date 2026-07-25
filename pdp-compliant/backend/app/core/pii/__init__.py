from __future__ import annotations

import logging

from app.config import settings
from app.core.pii.detectors import detect_rule_based, drop_overlaps
from app.core.pii.ner import detect_freetext
from app.models.schemas import DetectionResult, PIIEntity

logger = logging.getLogger("sentinel.pii")


class DetectionFailedError(Exception):
    """Raised so callers fail closed (F2.6): the document must not proceed."""


def _merge(rule_entities: list[PIIEntity], ner_entities: list[PIIEntity]) -> list[PIIEntity]:
    """Resolve overlaps across BOTH detector families in one pass. This is
    not just a quality nicety: pseudonymize() replaces spans by raw offset,
    so any surviving overlap would corrupt the tokenized output."""
    return drop_overlaps(list(rule_entities) + list(ner_entities))


def detect_all(text: str) -> DetectionResult:
    """F2.1-F2.7: combined rule-based + model-based Indonesian PII detection.

    Fails closed: any exception propagates as DetectionFailedError rather
    than being swallowed into an empty/partial result.
    """
    try:
        rule_entities = detect_rule_based(text)
        ner_entities = detect_freetext(text)
    except Exception as exc:  # noqa: BLE001 - intentional fail-closed boundary
        logger.error("PII detection failed; document will not proceed: %s", exc)
        raise DetectionFailedError(str(exc)) from exc

    entities = _merge(rule_entities, ner_entities)
    min_confidence = min((e.confidence for e in entities), default=1.0)
    below_floor = min_confidence < settings.detection_confidence_floor if entities else False

    return DetectionResult(
        entities=entities,
        min_confidence=min_confidence,
        below_floor=below_floor,
    )
