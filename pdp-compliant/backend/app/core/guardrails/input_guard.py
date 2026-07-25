"""
Input guardrails (F6.1, F6.2). Complaint text is untrusted, attacker-authored
input — it reaches this guard already tokenized (post-pseudonymization), but
tokenization does not neutralize injection attempts, so this check still
matters.

This is a keyword/pattern baseline sized for the Phase 4 red-team corpus
(§10.4) to score against, not a production-grade classifier. M3 (≥95% catch
rate) is the number that tells you whether this needs to become a real
classifier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.config import settings

_INJECTION_PATTERNS = [
    # English
    r"ignore (all|any|the) (previous|prior|above) instructions?",
    r"disregard (all|any|the) (previous|prior|above)",
    r"you are now",
    r"act as (a|an)\b",
    r"system prompt",
    r"reveal (your|the) (prompt|instructions)",
    r"new instructions?:",
    r"override (your|the) (rules|guidelines|instructions)",
    r"pretend (you are|to be)",
    r"do anything now",
    # Indonesian
    r"abaikan (semua|instruksi) (sebelumnya|di atas)",
    r"lupakan (instruksi|perintah) (sebelumnya|sebelum ini)",
    r"kamu (sekarang|adalah)",
    r"berperan sebagai",
    r"tampilkan (prompt|instruksi)",
    r"instruksi baru\s*:",
    r"abaikan (aturan|panduan)",
    r"berikan (semua )?data (asli|sebenarnya)",
    r"ungkapkan token",
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

_ABUSE_PATTERNS = [
    r"\bbunuh\b", r"\bbakar (kantor|cabang|rumah)\b", r"\bancam\b", r"\bhancurkan\b",
    r"\bkill you\b", r"\bi will burn\b", r"\bthreaten\b", r"\bi'll destroy\b",
]
_ABUSE_RE = re.compile("|".join(_ABUSE_PATTERNS), re.IGNORECASE)


@dataclass
class InputGuardResult:
    injection_detected: bool
    injection_score: float
    abuse_detected: bool
    triggered_rules: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.injection_score >= settings.injection_block_threshold

    @property
    def flags(self) -> list[str]:
        flags = []
        if self.injection_detected:
            flags.append("input_guard:injection")
        if self.abuse_detected:
            flags.append("input_guard:abuse")
        return flags


def check_input(tokenized_text: str) -> InputGuardResult:
    injection_matches = _INJECTION_RE.findall(tokenized_text)
    abuse_matches = _ABUSE_RE.findall(tokenized_text)

    triggered = []
    if injection_matches:
        triggered.append(f"injection_pattern_match:{len(injection_matches)}")
    if abuse_matches:
        triggered.append(f"abuse_pattern_match:{len(abuse_matches)}")

    # Coarse scoring: any hit is meaningful given these are high-precision
    # patterns; more hits raise confidence rather than gating on count alone.
    injection_score = min(1.0, 0.85 + 0.05 * (len(injection_matches) - 1)) if injection_matches else 0.0

    return InputGuardResult(
        injection_detected=bool(injection_matches),
        injection_score=injection_score,
        abuse_detected=bool(abuse_matches),
        triggered_rules=triggered,
    )
