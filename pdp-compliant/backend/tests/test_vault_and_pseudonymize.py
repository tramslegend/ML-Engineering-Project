import tempfile
from pathlib import Path

import pytest

from app.core.pii import detect_all
from app.core.reidentify import reidentify
from app.core.vault.pseudonymize import pseudonymize
from app.core.vault.store import VaultStore


@pytest.fixture
def vault(tmp_path: Path) -> VaultStore:
    return VaultStore(db_path=tmp_path / "vault_test.db", encryption_key="test-key")


def test_pseudonymize_referential_consistency(vault):
    # Realistic complaint phrasing (name introduced via a cue, per how the
    # heuristic NER in ner.py is designed to be used — see that module's
    # docstring on sentence-initial bare names being an intentional gap).
    text = "Nama saya Budi Santoso. Budi Santoso adalah nasabah kami."
    detection = detect_all(text)
    result = pseudonymize(text, detection, job_id="job1", vault=vault)
    # Both mentions of the same name should collapse to the same token.
    assert result.tokenized_text.count("[ORANG_1]") == 2
    assert "Budi Santoso" not in result.tokenized_text


def test_pseudonymize_and_reidentify_roundtrip(vault):
    text = "NIK saya 3171012303900021, telepon saya 081234567890."
    detection = detect_all(text)
    result = pseudonymize(text, detection, job_id="job2", vault=vault)
    assert "3171012303900021" not in result.tokenized_text
    assert "081234567890" not in result.tokenized_text

    restored, resolved = reidentify(
        result.tokenized_text,
        subject_id=result.subject_id,
        job_id="job2",
        actor="test-actor",
        justification="unit test",
        vault=vault,
    )
    assert "3171012303900021" in restored
    assert "081234567890" in restored
    assert len(resolved) == 2


def test_partial_reidentify_leaves_other_tokens(vault):
    from app.models.schemas import EntityType

    text = "NIK saya 3171012303900021, telepon saya 081234567890."
    detection = detect_all(text)
    result = pseudonymize(text, detection, job_id="job3", vault=vault)

    restored, resolved = reidentify(
        result.tokenized_text,
        subject_id=result.subject_id,
        job_id="job3",
        actor="test-actor",
        justification="unit test",
        fields=[EntityType.PHONE],
        vault=vault,
    )
    assert "081234567890" in restored
    assert "3171012303900021" not in restored  # NIK token must remain unresolved
    assert resolved == [EntityType.PHONE]


def test_erasure_orphans_tokens(vault):
    text = "NIK saya 3171012303900021."
    detection = detect_all(text)
    result = pseudonymize(text, detection, job_id="job4", vault=vault)

    erased_count = vault.erase_subject(result.subject_id)
    assert erased_count == 1

    restored, resolved = reidentify(
        result.tokenized_text,
        subject_id=result.subject_id,
        job_id="job4",
        actor="test-actor",
        justification="post-erasure check",
        vault=vault,
    )
    assert resolved == []
    assert "3171012303900021" not in restored
    assert "[NIK_1]" in restored  # token left in place, unresolvable


def test_no_cross_document_linkage(vault):
    """F3.3: the same real person tokenizes independently across two calls —
    subject_id must differ, so there is no way to link the two documents via
    the vault."""
    text = "NIK saya 3171012303900021."
    d1 = pseudonymize(text, detect_all(text), job_id="jobA", vault=vault)
    d2 = pseudonymize(text, detect_all(text), job_id="jobB", vault=vault)
    assert d1.subject_id != d2.subject_id
