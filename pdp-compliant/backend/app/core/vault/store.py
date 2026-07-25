"""
Token vault (F3.4-F3.6). Local stand-in for DynamoDB + KMS CMK in
`ap-southeast-3` — see infra/modules/vault for the target Terraform.

F3.5: "No human IAM principal has read access in normal operation." There is
no IAM to enforce that locally; this module is the single choke point real
access control would sit behind, and callers outside `core/vault` and
`core/reidentify` must not import `VaultStore` directly. That boundary is
enforced by code review here, not by the runtime — flagged as a gap, not
hidden as solved.
"""
from __future__ import annotations

import base64
import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet

from app.config import settings
from app.models.schemas import EntityType


def _derive_fernet_key(passphrase: str) -> bytes:
    """Dev-only KDF stand-in for a KMS CMK. Real deployment: KMS-managed key,
    never a passphrase derived in application code."""
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class VaultStore:
    def __init__(self, db_path: Path | None = None, encryption_key: str | None = None):
        self._db_path = db_path or settings.vault_db_path
        self._fernet = Fernet(_derive_fernet_key(encryption_key or settings.vault_encryption_key))
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vault_entries (
                    token TEXT PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    real_value_encrypted BLOB NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_subject ON vault_entries (subject_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_job ON vault_entries (job_id)")

    @staticmethod
    def new_subject_id() -> str:
        return f"subj_{uuid.uuid4().hex[:16]}"

    def put(self, *, token: str, subject_id: str, job_id: str, entity_type: EntityType, real_value: str) -> None:
        encrypted = self._fernet.encrypt(real_value.encode("utf-8"))
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO vault_entries (token, subject_id, job_id, entity_type, real_value_encrypted, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET real_value_encrypted = excluded.real_value_encrypted
                """,
                (token, subject_id, job_id, entity_type.value, encrypted, datetime.now(timezone.utc).isoformat()),
            )

    def get(self, token: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT real_value_encrypted FROM vault_entries WHERE token = ?", (token,)
            ).fetchone()
        if row is None:
            return None
        return self._fernet.decrypt(row[0]).decode("utf-8")

    def get_many(self, tokens: list[str]) -> dict[str, str]:
        return {t: v for t in tokens if (v := self.get(t)) is not None}

    def tokens_for_job(self, job_id: str) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT token FROM vault_entries WHERE job_id = ?", (job_id,)).fetchall()
        return [r[0] for r in rows]

    def erase_subject(self, subject_id: str) -> int:
        """F3.6 / N19: single-call erasure. Deleting a subject's vault entries
        orphans every derived token system-wide — nothing downstream can
        re-identify without this row. Must complete within 24h of request (N19);
        this call is synchronous and immediate."""
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM vault_entries WHERE subject_id = ?", (subject_id,))
            return cur.rowcount


_default_store: VaultStore | None = None


def get_vault_store() -> VaultStore:
    global _default_store
    if _default_store is None:
        _default_store = VaultStore()
    return _default_store
