"""
Output guardrails (F6.3-F6.6). Runs on model output — local or escalation
tier — before it reaches an analyst.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.schemas import TriageOutput

_FINANCIAL_ADVICE_PATTERNS = [
    r"\b(saya sarankan|kami sarankan) anda (membeli|menjual|investasi)",
    r"\bi (recommend|suggest) (you )?(buy|sell|invest)",
    r"\bpindahkan dana anda ke\b",
    r"\bmove your (money|funds) (into|to)\b",
    r"\bbeli saham\b|\bbuy stock\b",
]
_FINANCIAL_ADVICE_RE = re.compile("|".join(_FINANCIAL_ADVICE_PATTERNS), re.IGNORECASE)

_COMPENSATION_PATTERNS = [
    r"\b(kami akan|bank akan) (mengganti|mengembalikan|memberikan kompensasi)\b",
    r"\bwe will (refund|reimburse|compensate)\b",
    r"\bfull refund (is )?guaranteed\b",
    r"\bkompensasi (penuh )?akan diberikan\b",
    r"\bdana anda akan dikembalikan\b",
]
_COMPENSATION_RE = re.compile("|".join(_COMPENSATION_PATTERNS), re.IGNORECASE)

_TOKEN_RE = re.compile(r"\[[A-Z_]+_\d+\]")


@dataclass
class OutputGuardResult:
    financial_advice_detected: bool = False
    compensation_commitment_detected: bool = False
    ungrounded_claim: bool = False
    leaked_tokens: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(
            self.financial_advice_detected
            or self.compensation_commitment_detected
            or self.ungrounded_claim
            or self.leaked_tokens
        )

    @property
    def flags(self) -> list[str]:
        flags = []
        if self.financial_advice_detected:
            flags.append("output_guard:financial_advice")
        if self.compensation_commitment_detected:
            flags.append("output_guard:compensation_commitment")
        if self.ungrounded_claim:
            flags.append("output_guard:ungrounded_claim")
        if self.leaked_tokens:
            flags.append("output_guard:token_leakage")
        return flags


def check_grounding(draft_response: str, grounding_context: list[str] | None) -> bool:
    """F6.5: block responses citing policy not present in retrieved context.

    Scaffold behavior: with no policy corpus/RAG wired up yet (S3 Vectors in
    §9/§11 is not deployed in this scaffold), any response that makes a
    policy citation (a "berdasarkan kebijakan" / "according to policy" style
    claim) without supplied grounding_context is treated conservatively as
    ungrounded. Once the policy corpus is live, this should check textual
    entailment/citation against the retrieved chunks, not just presence.
    """
    cites_policy = bool(re.search(r"berdasarkan kebijakan|sesuai kebijakan|according to (our )?polic(y|ies)",
                                   draft_response, re.IGNORECASE))
    if not cites_policy:
        return False
    return not grounding_context


def check_output(triage: TriageOutput, grounding_context: list[str] | None = None) -> OutputGuardResult:
    text = f"{triage.summary}\n{triage.draft_response}"
    result = OutputGuardResult()

    if _FINANCIAL_ADVICE_RE.search(text):
        result.financial_advice_detected = True
        result.triggered_rules.append("financial_advice")

    if _COMPENSATION_RE.search(text):
        result.compensation_commitment_detected = True
        result.triggered_rules.append("compensation_commitment")

    if check_grounding(triage.draft_response, grounding_context):
        result.ungrounded_claim = True
        result.triggered_rules.append("ungrounded_policy_claim")

    # F6.6: "any unresolved token in a customer-facing draft is a defect" —
    # that's draft_response specifically. `summary` is an internal
    # analyst-facing field and legitimately contains tokens until the
    # analyst re-identifies (F7); flagging it here would false-positive on
    # every single complaint.
    leaked = _TOKEN_RE.findall(triage.draft_response)
    if leaked:
        result.leaked_tokens = leaked
        result.triggered_rules.append(f"token_leakage:{len(leaked)}")

    return result
