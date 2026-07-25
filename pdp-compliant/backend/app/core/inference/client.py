"""
Local model inference client (F4).

F4.1/F4.2: serves the local model in-region, accepts only tokenized text —
callers in the pipeline are responsible for never passing this module raw
text (enforced by the pipeline calling pseudonymize() first, and by the CI
invariant described in PRD §6.1).

F4.5: a timeout here must escalate, not fail the request. This client raises
`LocalInferenceUnavailable` for both timeouts and connection errors; the
escalation router (core/escalation/router.py) is the only place that decides
what happens next.

F4.6: hot-swapping the model is just changing `settings.local_inference_model`
(env var) — no redeploy, because the model name is a request parameter to the
inference server, not something baked into this client.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Protocol

import httpx

from app.config import settings
from app.models.schemas import InferenceTier, Severity, TriageOutput

logger = logging.getLogger("sentinel.inference")

_SYSTEM_PROMPT = """You are a triage assistant for an Indonesian bank's complaint intake.
You receive complaint text with all personal data replaced by tokens like [ORANG_1], [NIK_1].
Never attempt to guess or reconstruct the real values behind a token.
Respond with ONLY a JSON object matching this schema:
{
  "category": string,
  "severity": "low" | "medium" | "high" | "critical",
  "summary": string,
  "draft_response": string (must not promise compensation, refunds, or give financial advice),
  "multi_issue": boolean,
  "field_confidence": {"category": float, "severity": float, "draft_response": float},
  "overall_confidence": float
}"""


class LocalInferenceUnavailable(Exception):
    """Local tier could not produce a result (timeout, connection error,
    malformed output). Per F4.5/F5.1, the caller must escalate, not fail."""


class InferenceClient(Protocol):
    def classify(self, tokenized_text: str) -> TriageOutput: ...


class OllamaCompatibleClient:
    """Targets an Ollama-compatible `/api/generate` endpoint, which is how a
    GGUF build of SEA-LION v4 4B (or the Phase 2 benchmark's other
    candidates) would be served on the CPU Fargate/EC2 target in §11."""

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout_s: float | None = None):
        self._base_url = (base_url or settings.local_inference_url).rstrip("/")
        self._model = model or settings.local_inference_model
        self._timeout_s = timeout_s or settings.local_inference_timeout_s

    def classify(self, tokenized_text: str) -> TriageOutput:
        prompt = f"{_SYSTEM_PROMPT}\n\nComplaint:\n{tokenized_text}\n\nJSON:"
        start = time.monotonic()
        try:
            resp = httpx.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False, "format": "json"},
                timeout=self._timeout_s,
            )
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LocalInferenceUnavailable(f"local inference timeout after {self._timeout_s}s") from exc
        except httpx.HTTPError as exc:
            raise LocalInferenceUnavailable(f"local inference unreachable: {exc}") from exc

        elapsed = time.monotonic() - start
        logger.info("local inference (%s) responded in %.2fs", self._model, elapsed)

        try:
            payload = json.loads(resp.json()["response"])
            return TriageOutput(**payload, tier_used=InferenceTier.LOCAL)
        except Exception as exc:  # noqa: BLE001 - schema/parse failure -> escalate per F5.1
            raise LocalInferenceUnavailable(f"local inference output failed schema validation: {exc}") from exc


class MockInferenceClient:
    """Dev-only stand-in so the pipeline is runnable without a live model
    server. Used when SENTINEL_LOCAL_INFERENCE_URL is unset/unreachable AND
    the caller explicitly opts into mock mode — never a silent fallback in
    the real request path, since silently masking local-tier outages would
    violate F5.1's escalation trigger."""

    _KEYWORDS_HIGH = ("penipuan", "fraud", "dibobol", "hilang", "kecurian", "ancam")
    _KEYWORDS_MEDIUM = ("error", "gagal", "tidak bisa", "lambat", "komplain")

    def classify(self, tokenized_text: str) -> TriageOutput:
        lowered = tokenized_text.lower()
        if any(k in lowered for k in self._KEYWORDS_HIGH):
            severity = Severity.HIGH
            category = "potential_fraud"
        elif any(k in lowered for k in self._KEYWORDS_MEDIUM):
            severity = Severity.MEDIUM
            category = "service_issue"
        else:
            severity = Severity.LOW
            category = "general_inquiry"

        return TriageOutput(
            category=category,
            severity=severity,
            summary=tokenized_text[:160],
            draft_response=(
                "Terima kasih atas laporan Anda. Tim kami akan meninjau keluhan ini "
                "dan menindaklanjuti sesuai prosedur yang berlaku."
            ),
            multi_issue=False,
            field_confidence={"category": 0.55, "severity": 0.55, "draft_response": 0.55},
            overall_confidence=0.55,
            tier_used=InferenceTier.LOCAL,
        )


def get_local_inference_client(use_mock: bool = False) -> InferenceClient:
    if use_mock:
        return MockInferenceClient()
    return OllamaCompatibleClient()
