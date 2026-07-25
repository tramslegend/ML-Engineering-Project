"""
Pseudonymization (F3.1-F3.3): replace detected entities with typed, numbered
tokens, preserving referential structure within a document, and persist the
mapping to the vault.
"""
from __future__ import annotations

from app.core.vault.store import VaultStore, get_vault_store
from app.models.schemas import DetectionResult, PseudonymizationResult, TokenSpan


def pseudonymize(
    text: str,
    detection: DetectionResult,
    *,
    job_id: str,
    vault: VaultStore | None = None,
) -> PseudonymizationResult:
    """F3.2: repeated mentions of the same entity within THIS document reuse
    the same token (matched by normalized raw text + entity type).
    F3.3: no cross-document linkage — a fresh subject_id per call, never
    reused across jobs, so the same real person tokenizes differently in a
    different complaint."""
    vault = vault or get_vault_store()
    subject_id = VaultStore.new_subject_id()

    counters: dict[str, int] = {}
    seen_tokens: dict[tuple[str, str], str] = {}  # (entity_type, normalized_text) -> token
    spans: list[TokenSpan] = []

    # Process in reverse start order so earlier replacements don't shift later offsets.
    ordered = sorted(detection.entities, key=lambda e: e.start, reverse=True)
    result_text = text

    for entity in ordered:
        key = (entity.entity_type.value, entity.raw_text.strip().lower())
        token = seen_tokens.get(key)
        if token is None:
            counters[entity.entity_type.value] = counters.get(entity.entity_type.value, 0) + 1
            token = f"[{entity.entity_type.value}_{counters[entity.entity_type.value]}]"
            seen_tokens[key] = token
            vault.put(
                token=f"{subject_id}:{token}",
                subject_id=subject_id,
                job_id=job_id,
                entity_type=entity.entity_type,
                real_value=entity.raw_text,
            )
        result_text = result_text[: entity.start] + token + result_text[entity.end :]

    # Recompute spans by locating each token in the final tokenized text.
    spans = []
    for (entity_type_val, _norm_text), token in seen_tokens.items():
        idx = result_text.find(token)
        if idx != -1:
            spans.append(TokenSpan(token=token, entity_type=entity_type_val, start=idx, end=idx + len(token)))

    return PseudonymizationResult(tokenized_text=result_text, tokens=spans, subject_id=subject_id)
