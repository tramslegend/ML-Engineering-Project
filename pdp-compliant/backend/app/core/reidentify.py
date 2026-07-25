"""
Re-identification (F7). The only place tokens are resolved back to real
values. §6.1 invariant: this executes only in Zone A, and callers into this
module are exactly the set of things allowed to see real personal data.
"""
from __future__ import annotations

import re

from app.core.audit.log import log_event
from app.core.vault.store import VaultStore, get_vault_store
from app.models.schemas import EntityType

_TOKEN_RE = re.compile(r"\[([A-Z_]+)_(\d+)\]")


class ReidentifyError(Exception):
    pass


def reidentify(
    tokenized_text: str,
    *,
    subject_id: str,
    job_id: str,
    actor: str,
    justification: str,
    fields: list[EntityType] | None = None,
    vault: VaultStore | None = None,
) -> tuple[str, list[EntityType]]:
    """F7.1-F7.5.

    `fields`, if given, restricts resolution to those entity types (F7.5
    partial re-identification) — tokens for other types are left in place.

    F7.3: every call logs actor, subject, timestamp, justification.
    F7.4: this function's return value MUST NOT be written to logs, traces,
    metrics, or any observability sink by its caller — only to the analyst
    response body.
    """
    vault = vault or get_vault_store()
    allowed_types = {f.value for f in fields} if fields else None

    resolved_types: list[EntityType] = []

    def _resolve(match: re.Match) -> str:
        entity_type_str, _num = match.group(1), match.group(2)
        if allowed_types is not None and entity_type_str not in allowed_types:
            return match.group(0)
        vault_key = f"{subject_id}:{match.group(0)}"
        real_value = vault.get(vault_key)
        if real_value is None:
            return match.group(0)  # token not in vault (e.g. already erased) - leave as-is
        try:
            resolved_types.append(EntityType(entity_type_str))
        except ValueError:
            pass
        return real_value

    reidentified_text = _TOKEN_RE.sub(_resolve, tokenized_text)

    log_event(
        event_type="reidentify.access",
        actor=actor,
        subject_id=subject_id,
        job_id=job_id,
        justification=justification,
        detail={"fields_requested": [f.value for f in fields] if fields else "all",
                "fields_resolved": [f.value for f in set(resolved_types)]},
    )

    return reidentified_text, list(set(resolved_types))
