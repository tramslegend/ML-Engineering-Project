"""F3.6/N19: right-to-erasure. A single vault delete orphans every derived
token for the subject — reidentify() already treats a missing vault entry as
"leave the token as-is," so no downstream cleanup is required for the
guarantee to hold (M9)."""
from __future__ import annotations

from app.core.audit.log import log_event
from app.core.vault.store import VaultStore, get_vault_store


def erase_subject(subject_id: str, *, actor: str, justification: str, vault: VaultStore | None = None) -> int:
    vault = vault or get_vault_store()
    erased_count = vault.erase_subject(subject_id)
    log_event(
        event_type="erasure.completed",
        actor=actor,
        subject_id=subject_id,
        justification=justification,
        detail={"tokens_orphaned": erased_count},
    )
    return erased_count
