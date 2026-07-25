"""
Heuristic baseline recognizer for free-text PII: person names, addresses,
employer/institution (Appendix A).

These are explicitly the hard cases — "Structured identifiers are near-solved
by validation logic; free-text entities carry essentially all of the residual
recall risk." This module is a context-cue + capitalization heuristic, good
enough to exercise the full pipeline and to give the Phase 0 eval harness
something to score. It is NOT the Indonesian-tuned NER model F2.3 calls for.

Swap point for Phase 1 hardening: replace `detect_names`/`detect_addresses`
internals with calls to an Indonesian NER model (e.g. an IndoBERT-NER
checkpoint), keeping `detect_freetext` as the public interface so nothing
downstream changes.
"""
from __future__ import annotations

import re

from app.models.schemas import EntityType, PIIEntity

_NAME_CONTEXT = re.compile(
    r"(?:nama(?:\s+lengkap)?(?:\s+(?:saya|kami)\s+adalah|\s+(?:saya|kami))?|saya\s+bernama|"
    r"sdr\.?|sdri\.?|bapak|ibu|saudara|a\.?n\.?|atas nama)\s*[:.]?\s*",
    re.IGNORECASE,
)
# A run of Title-Case tokens (handles mononyms — a single token qualifies).
# Deliberately excludes '.' from the token class so a run can't swallow a
# sentence boundary (e.g. "Baru. Nomor" must not match as one span).
_CAP_RUN = re.compile(r"\b[A-Z][a-zA-Z']*(?:\s+[A-Z][a-zA-Z']*){0,4}\b")

_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+)\s*$")


def detect_names(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    known_names: set[str] = set()

    # High-confidence: capitalized run immediately after a name-introducing cue.
    for cue in _NAME_CONTEXT.finditer(text):
        window = text[cue.end():cue.end() + 60]
        m = _CAP_RUN.match(window)
        if m:
            start, end = cue.end() + m.start(), cue.end() + m.end()
            entities.append(PIIEntity(
                entity_type=EntityType.PERSON_NAME, start=start, end=end,
                raw_text=text[start:end], confidence=0.88, detector="ner",
            ))
            known_names.add(m.group(0))

    # F3.2 referential consistency: re-mentions of a name already confirmed
    # by a cue are common at the START of a later sentence ("Budi Santoso
    # melapor... Budi Santoso adalah nasabah kami.") — exactly where the
    # sentence-initial guard below would otherwise suppress them. Since
    # these are exact-string matches of an already-cue-confirmed name, the
    # sentence-initial exclusion doesn't apply to them; the risk it guards
    # against (an arbitrary capitalized sentence-starter) doesn't exist once
    # we already know this specific string is a name.
    for name in known_names:
        for m in re.finditer(re.escape(name), text):
            if any(e.start <= m.start() < e.end for e in entities):
                continue
            entities.append(PIIEntity(
                entity_type=EntityType.PERSON_NAME, start=m.start(), end=m.end(),
                raw_text=m.group(0), confidence=0.85, detector="ner",
            ))

    # Lower-confidence fallback: capitalized multi-word run not at sentence start
    # (crude proxy for "probably a proper noun, not a sentence-initial word").
    # Known gap: a name that is NEVER introduced via a cue anywhere in the
    # document, and whose first occurrence also happens to be sentence-
    # initial (e.g. a document that opens cold with "Budi Santoso melapor
    # bahwa...", no "Nama saya" anywhere), is missed entirely — there's no
    # known_names entry to re-match against, and the fallback below excludes
    # sentence-initial spans. Real complaints observed for this PRD are
    # consistently self-introduced via a cue at least once, so this is a
    # low-frequency gap in practice — but it is a gap, not a false claim of
    # full coverage.
    for m in _CAP_RUN.finditer(text):
        if " " not in m.group(0):
            continue  # single capitalized word alone is too noisy without a cue
        preceding = text[max(0, m.start() - 15):m.start()]
        if _SENTENCE_START.search(preceding):
            continue
        if any(e.start <= m.start() < e.end for e in entities):
            continue
        entities.append(PIIEntity(
            entity_type=EntityType.PERSON_NAME, start=m.start(), end=m.end(),
            raw_text=m.group(0), confidence=0.45, detector="ner",
        ))
    return entities


_ADDRESS_KEYWORDS = re.compile(
    r"\b(?:jl\.?|jalan|rt\s?\d{1,3}\s?/?\s?rw\s?\d{1,3}|kelurahan|kel\.?|kecamatan|kec\.?|"
    r"kabupaten|kab\.?|kota|provinsi)\b",
    re.IGNORECASE,
)


def detect_addresses(text: str) -> list[PIIEntity]:
    """Grab a bounded window around address keywords rather than the whole line,
    to avoid swallowing unrelated sentence content."""
    entities: list[PIIEntity] = []
    for m in _ADDRESS_KEYWORDS.finditer(text):
        window_start = m.start()
        window_end = min(len(text), m.end() + 80)
        # stop the window at the next sentence boundary if there is one
        stop = re.search(r"[.\n]", text[m.end():window_end])
        window_end = m.end() + stop.start() if stop else window_end
        span_text = text[window_start:window_end].strip()
        if not span_text:
            continue
        real_start = window_start + (len(text[window_start:window_end]) - len(text[window_start:window_end].lstrip()))
        entities.append(PIIEntity(
            entity_type=EntityType.ADDRESS, start=real_start, end=real_start + len(span_text),
            raw_text=span_text, confidence=0.60, detector="ner",
        ))
    return entities


_EMPLOYER_CONTEXT = re.compile(
    r"(?:bekerja di|karyawan|pegawai|kantor)\s+(?:PT\.?|CV\.?|Bank)?\s*",
    re.IGNORECASE,
)
_EMPLOYER_NAME_RE = re.compile(r"(?:PT\.?|CV\.?|Bank)?\s*[A-Z][a-zA-Z0-9&.]*(?:\s+[A-Z][a-zA-Z0-9&.]*){0,3}")


def detect_employer(text: str) -> list[PIIEntity]:
    entities: list[PIIEntity] = []
    for cue in _EMPLOYER_CONTEXT.finditer(text):
        window = text[cue.end():cue.end() + 50]
        m = _EMPLOYER_NAME_RE.match(window)
        if m and m.group(0).strip():
            start, end = cue.end() + m.start(), cue.end() + m.end()
            entities.append(PIIEntity(
                entity_type=EntityType.EMPLOYER, start=start, end=end,
                raw_text=text[start:end].strip(), confidence=0.50, detector="ner",
            ))
    return entities


def detect_freetext(text: str) -> list[PIIEntity]:
    """F2.3 model-based recognizer surface. See module docstring for the
    swap point to a real Indonesian NER model."""
    return detect_names(text) + detect_addresses(text) + detect_employer(text)
