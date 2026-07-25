"""
Escalation-tier (frontier model) provider clients (F5, §6.3 Zone C).

N10: real deployment reads provider keys from Secrets Manager via the
Parameters and Secrets Lambda Extension, never from environment variables
directly. This module reads from `settings` (which is itself sourced from
env/`.env` locally) as the swap point — replace `_get_api_key` with a
Secrets Manager call in Phase 3, nothing else in this module should change.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings
from app.models.schemas import InferenceTier, Severity, TriageOutput

_SYSTEM_PROMPT = """You are a triage assistant for an Indonesian bank's complaint intake.
You receive complaint text with all personal data replaced by tokens like [ORANG_1], [NIK_1].
Never attempt to guess or reconstruct the real values behind a token. Never invent, echo, or
complete a token with real-looking data.
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


class EscalationError(Exception):
    pass


@dataclass
class EscalationUsage:
    provider: str
    tokens_in: int
    tokens_out: int
    latency_s: float
    estimated_cost_usd: float


class EscalationProvider(Protocol):
    name: str

    def classify(self, tokenized_text: str) -> tuple[TriageOutput, EscalationUsage]: ...


class DeepSeekProvider:
    """Frontier tier via DeepSeek's OpenAI-compatible chat completions API."""

    name = "deepseek"
    _PRICE_PER_1K_IN = 0.00027   # indicative; refresh from provider pricing page before publishing M6
    _PRICE_PER_1K_OUT = 0.00110

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None, timeout_s: float = 30.0):
        self._api_key = api_key or settings.deepseek_api_key
        self._base_url = base_url or settings.deepseek_base_url
        self._model = model or settings.deepseek_model
        self._timeout_s = timeout_s

    def classify(self, tokenized_text: str) -> tuple[TriageOutput, EscalationUsage]:
        if not self._api_key:
            raise EscalationError("DEEPSEEK_API_KEY not configured (backend/.env)")
        start = time.monotonic()
        try:
            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": tokenized_text},
                    ],
                    "response_format": {"type": "json_object"},
                },
                timeout=self._timeout_s,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise EscalationError(f"DeepSeek request failed: {exc}") from exc

        body = resp.json()
        content = json.loads(body["choices"][0]["message"]["content"])
        triage = TriageOutput(**content, tier_used=InferenceTier.ESCALATION)

        usage = body.get("usage", {})
        tokens_in, tokens_out = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        cost = (tokens_in / 1000) * self._PRICE_PER_1K_IN + (tokens_out / 1000) * self._PRICE_PER_1K_OUT
        return triage, EscalationUsage(
            provider=self.name, tokens_in=tokens_in, tokens_out=tokens_out,
            latency_s=time.monotonic() - start, estimated_cost_usd=round(cost, 6),
        )


class MockEscalationProvider:
    """Dev-only stand-in — same rationale as MockInferenceClient. Lets the
    escalation path (routing, circuit breaker, cost ledger, audit log) be
    exercised end to end without a live provider key."""

    name = "mock"

    def classify(self, tokenized_text: str) -> tuple[TriageOutput, EscalationUsage]:
        start = time.monotonic()
        triage = TriageOutput(
            category="escalated_review",
            severity=Severity.MEDIUM,
            summary=tokenized_text[:160],
            draft_response=(
                "Terima kasih telah menghubungi kami. Keluhan Anda telah ditinjau lebih lanjut "
                "dan akan ditindaklanjuti oleh tim terkait."
            ),
            multi_issue=False,
            field_confidence={"category": 0.80, "severity": 0.80, "draft_response": 0.80},
            overall_confidence=0.80,
            tier_used=InferenceTier.ESCALATION,
        )
        approx_tokens_in = max(1, len(tokenized_text) // 4)
        approx_tokens_out = max(1, len(triage.draft_response) // 4)
        return triage, EscalationUsage(
            provider=self.name, tokens_in=approx_tokens_in, tokens_out=approx_tokens_out,
            latency_s=time.monotonic() - start, estimated_cost_usd=0.0,
        )


def get_provider(name: str, use_mock: bool = False) -> EscalationProvider:
    if use_mock:
        return MockEscalationProvider()
    providers = {"deepseek": DeepSeekProvider}
    if name not in providers:
        raise EscalationError(f"unknown escalation provider: {name}")
    return providers[name]()
