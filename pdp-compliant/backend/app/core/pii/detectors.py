"""
Indonesian PII detectors (F2, Appendix A).

Structured identifiers (NIK, NPWP, KK, BPJS, card, phone, email, plat nomor,
DOB) use rule-based / structural validation per F2.2 — these are
near-deterministic and should not depend on a model.

Free-text entities (name, address, employer) are the hard cases per Appendix
A's closing note. `ner.py` holds a heuristic baseline for those; a real
deployment should swap it for an Indonesian-tuned NER model without changing
this module's public interface (`detect_all`).

F2.6 (fail closed): callers must treat an exception from `detect_all` as
"document does not proceed," not as "zero entities found." This module
raises rather than swallowing errors for that reason.
"""
from __future__ import annotations

import re
from datetime import date

from app.models.schemas import EntityType, PIIEntity

# --- Indonesian province/regency codes for NIK structural validation ---
# First 2 digits of NIK are a valid BPS province code (11-94 range, sparse).
_VALID_PROVINCE_CODES = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "21", "31", "32",
    "33", "34", "35", "36", "51", "52", "53", "61", "62", "63", "64", "65",
    "71", "72", "73", "74", "75", "76", "81", "82", "91", "94",
}


def _valid_nik_date(digits: str) -> bool:
    """NIK digits 7-12 encode DDMMYY; female DOB has DD+40."""
    dd, mm, yy = int(digits[0:2]), int(digits[2:4]), int(digits[4:6])
    day = dd - 40 if dd > 40 else dd
    if not (1 <= day <= 31 and 1 <= mm <= 12):
        return False
    try:
        # Resolve a plausible century; NIK doesn't disambiguate 1930 vs 2030.
        date(2000 + yy if yy <= 30 else 1900 + yy, mm, min(day, 28) or 1)
    except ValueError:
        return False
    return True


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_DIGIT_RUN = re.compile(r"\d[\d.\-\s]{10,20}\d")


def _normalize_digits(s: str) -> str:
    return re.sub(r"[.\-\s]", "", s)


def detect_nik(text: str) -> list[PIIEntity]:
    """A 16-digit card number will occasionally also satisfy NIK's
    province+date structural check by coincidence (~1 in a few hundred). A
    real card number is Luhn-valid by construction; a real NIK is Luhn-valid
    only by chance (~1 in 10). So Luhn validity is itself evidence AGAINST
    the NIK interpretation, and confidence is discounted accordingly — this
    is what lets detect_card_and_account win the overlap-resolution tie in
    _drop_overlaps for genuine card numbers, instead of the digits getting
    mislabeled NIK (still redacted either way, but with the wrong entity
    type, which matters for F7.5 partial re-identification correctness)."""
    entities: list[PIIEntity] = []
    for m in re.finditer(r"\b\d{16}\b", text):
        digits = m.group(0)
        province_ok = digits[0:2] in _VALID_PROVINCE_CODES
        date_ok = _valid_nik_date(digits[6:12])
        luhn_coincidence = _luhn_valid(digits)
        if province_ok and date_ok:
            entities.append(PIIEntity(
                entity_type=EntityType.NIK, start=m.start(), end=m.end(),
                raw_text=digits, confidence=0.75 if luhn_coincidence else 0.98, detector="rule",
            ))
        elif date_ok:
            # plausible DOB encoding but unrecognized province code — still flag, lower confidence
            entities.append(PIIEntity(
                entity_type=EntityType.NIK, start=m.start(), end=m.end(),
                raw_text=digits, confidence=0.55, detector="rule",
            ))
    return entities


_NPWP_CONTEXT = re.compile(r"npwp", re.IGNORECASE)


def detect_npwp(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    # Formatted: XX.XXX.XXX.X-XXX.XXX (15 digit legacy) or 16-digit (post-2024, = NIK for individuals)
    for m in re.finditer(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b", text):
        entities.append(PIIEntity(
            entity_type=EntityType.NPWP, start=m.start(), end=m.end(),
            raw_text=m.group(0), confidence=0.95, detector="rule",
        ))
    for m in re.finditer(r"\b\d{15,16}\b", text):
        window = text[max(0, m.start() - 20):m.start()]
        if _NPWP_CONTEXT.search(window):
            entities.append(PIIEntity(
                entity_type=EntityType.NPWP, start=m.start(), end=m.end(),
                raw_text=m.group(0), confidence=0.75, detector="rule",
            ))
    return entities


_KK_CONTEXT = re.compile(r"kartu keluarga|nomor kk|no\.?\s*kk|no kk", re.IGNORECASE)


def detect_nomor_kk(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for m in re.finditer(r"\b\d{16}\b", text):
        window = text[max(0, m.start() - 30):m.start()]
        if _KK_CONTEXT.search(window):
            entities.append(PIIEntity(
                entity_type=EntityType.NOMOR_KK, start=m.start(), end=m.end(),
                raw_text=m.group(0), confidence=0.90, detector="rule",
            ))
    return entities


def detect_bpjs(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for m in re.finditer(r"\b\d{13}\b", text):
        window = text[max(0, m.start() - 20):m.start()]
        boost = 0.15 if re.search(r"bpjs", window, re.IGNORECASE) else 0.0
        entities.append(PIIEntity(
            entity_type=EntityType.BPJS, start=m.start(), end=m.end(),
            raw_text=m.group(0), confidence=min(0.99, 0.65 + boost), detector="rule",
        ))
    return entities


_CARD_CONTEXT = re.compile(r"kartu|visa|mastercard|debit|kredit", re.IGNORECASE)
_ACCOUNT_CONTEXT = re.compile(r"rekening|no\.?\s*rek|a\.?n\.?\s", re.IGNORECASE)


def detect_card_and_account(text: str) -> list[PIIEntity]:
    """Distinguish card numbers (Luhn-valid, card context) from bank accounts."""
    entities: list[PIIEntity] = []
    for m in re.finditer(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", text):
        digits = _normalize_digits(m.group(0))
        window = text[max(0, m.start() - 25):m.start()]
        if _luhn_valid(digits) and (_CARD_CONTEXT.search(window) or len(digits) == 16):
            entities.append(PIIEntity(
                entity_type=EntityType.CARD_NUMBER, start=m.start(), end=m.end(),
                raw_text=m.group(0), confidence=0.90 if _CARD_CONTEXT.search(window) else 0.70,
                detector="rule",
            ))
    for m in re.finditer(r"\b\d{8,16}\b", text):
        window = text[max(0, m.start() - 25):m.start()]
        if _ACCOUNT_CONTEXT.search(window):
            entities.append(PIIEntity(
                entity_type=EntityType.BANK_ACCOUNT, start=m.start(), end=m.end(),
                raw_text=m.group(0), confidence=0.80, detector="rule",
            ))
    return entities


_PHONE_RE = re.compile(r"(?<!\d)(?:\+62|62|0)8\d{8,11}(?!\d)")


def detect_phone(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for m in _PHONE_RE.finditer(text):
        entities.append(PIIEntity(
            entity_type=EntityType.PHONE, start=m.start(), end=m.end(),
            raw_text=m.group(0), confidence=0.92, detector="rule",
        ))
    return entities


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def detect_email(text: str) -> list[PIIEntity]:
    return [
        PIIEntity(
            entity_type=EntityType.EMAIL, start=m.start(), end=m.end(),
            raw_text=m.group(0), confidence=0.97, detector="rule",
        )
        for m in _EMAIL_RE.finditer(text)
    ]


# Regional single/double letter prefixes are numerous; accept 1-2 uppercase
# letters, 1-4 digits, 1-3 uppercase letters, as the general plat nomor shape.
_PLAT_RE = re.compile(r"\b[A-Z]{1,2}\s?\d{1,4}\s?[A-Z]{1,3}\b")


def detect_plat_nomor(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for m in _PLAT_RE.finditer(text):
        entities.append(PIIEntity(
            entity_type=EntityType.PLAT_NOMOR, start=m.start(), end=m.end(),
            raw_text=m.group(0), confidence=0.65, detector="rule",
        ))
    return entities


_MONTHS_ID = (
    "januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember"
)
_DOB_CONTEXT = re.compile(r"lahir|tanggal lahir|tgl lahir|ttl", re.IGNORECASE)
_DOB_NUMERIC_RE = re.compile(r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b")
_DOB_TEXTUAL_RE = re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTHS_ID})\s+\d{{4}}\b", re.IGNORECASE)


def detect_date_of_birth(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for pattern in (_DOB_NUMERIC_RE, _DOB_TEXTUAL_RE):
        for m in pattern.finditer(text):
            window = text[max(0, m.start() - 25):m.start()]
            has_context = bool(_DOB_CONTEXT.search(window))
            entities.append(PIIEntity(
                entity_type=EntityType.DATE_OF_BIRTH, start=m.start(), end=m.end(),
                raw_text=m.group(0), confidence=0.85 if has_context else 0.45,
                detector="rule",
            ))
    return entities


_RULE_DETECTORS = (
    detect_nik,
    detect_npwp,
    detect_nomor_kk,
    detect_bpjs,
    detect_card_and_account,
    detect_phone,
    detect_email,
    detect_plat_nomor,
    detect_date_of_birth,
)


def drop_overlaps(entities: list[PIIEntity]) -> list[PIIEntity]:
    """Longer/higher-confidence spans win on overlap (e.g. NIK vs NPWP vs KK sharing 16 digits)."""
    ordered = sorted(entities, key=lambda e: (-(e.end - e.start), -e.confidence))
    kept: list[PIIEntity] = []
    occupied: list[tuple[int, int]] = []
    for e in ordered:
        if any(not (e.end <= s or e.start >= t) for s, t in occupied):
            continue
        kept.append(e)
        occupied.append((e.start, e.end))
    return sorted(kept, key=lambda e: e.start)


def detect_rule_based(text: str) -> list[PIIEntity]:
    """F2.2/F2.3: structured identifiers, no ML dependency."""
    found: list[PIIEntity] = []
    for detector in _RULE_DETECTORS:
        found.extend(detector(text))
    return drop_overlaps(found)
