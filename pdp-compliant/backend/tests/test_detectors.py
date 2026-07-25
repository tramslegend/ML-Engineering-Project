from app.core.pii import detect_all
from app.core.pii.detectors import detect_card_and_account, detect_nik, drop_overlaps
from app.models.schemas import EntityType


def test_nik_valid_structure_detected():
    entities = detect_nik("NIK saya 3171012303900021 ya.")
    assert len(entities) == 1
    assert entities[0].confidence >= 0.9


def test_nik_invalid_month_rejected():
    # day=01, month=13 (invalid), year=90 -> digits[6:12] == "011390"
    entities = detect_nik("NIK saya 3171010113900021 ya.")
    assert entities == []


def test_card_number_luhn_valid():
    entities = detect_card_and_account("Kartu saya nomor 4532015112830366 hilang.")
    card_matches = [e for e in entities if e.entity_type == EntityType.CARD_NUMBER]
    assert len(card_matches) == 1


def test_card_luhn_invalid_not_detected_as_card():
    # one digit off from a valid Luhn number
    entities = detect_card_and_account("Kartu saya nomor 4532015112830367 hilang.")
    card_matches = [e for e in entities if e.entity_type == EntityType.CARD_NUMBER]
    assert card_matches == []


def test_nik_card_collision_prefers_card_with_context():
    """Regression test: a 16-digit card number can coincidentally satisfy
    NIK's structural validation. With card context nearby, the card
    interpretation must win the overlap-resolution tie (see detect_nik's
    docstring for why Luhn validity is evidence against NIK)."""
    text = "Kartu saya nomor 9488375503758995 diblokir."
    result = detect_all(text)
    matched = [e for e in result.entities if e.raw_text == "9488375503758995"]
    assert len(matched) == 1
    assert matched[0].entity_type == EntityType.CARD_NUMBER


def test_phone_detected():
    entities = detect_all("Nomor saya 081234567890 ya pak.")
    phones = [e for e in entities.entities if e.entity_type == EntityType.PHONE]
    assert len(phones) == 1


def test_email_detected():
    entities = detect_all("Email saya budi@gmail.com untuk konfirmasi.")
    emails = [e for e in entities.entities if e.entity_type == EntityType.EMAIL]
    assert len(emails) == 1


def test_drop_overlaps_keeps_higher_confidence():
    from app.models.schemas import PIIEntity

    a = PIIEntity(entity_type=EntityType.NIK, start=0, end=16, raw_text="x" * 16, confidence=0.9, detector="rule")
    b = PIIEntity(entity_type=EntityType.CARD_NUMBER, start=0, end=16, raw_text="x" * 16, confidence=0.5, detector="rule")
    kept = drop_overlaps([a, b])
    assert len(kept) == 1
    assert kept[0].entity_type == EntityType.NIK


def test_detect_all_name_with_saya_cue():
    result = detect_all("Nama saya Budi Santoso, saya ingin komplain.")
    names = [e for e in result.entities if e.entity_type == EntityType.PERSON_NAME]
    assert any(e.raw_text == "Budi Santoso" and e.confidence >= 0.8 for e in names)
