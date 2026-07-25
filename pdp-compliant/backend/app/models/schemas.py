"""
Shared pydantic models. These double as the "published JSON schema" required
by F4.3 for local-model structured output.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- PII taxonomy (Appendix A) ---

class EntityType(str, Enum):
    NIK = "NIK"
    NPWP = "NPWP"
    NOMOR_KK = "NOMOR_KK"
    BPJS = "BPJS"
    BANK_ACCOUNT = "REKENING"
    CARD_NUMBER = "KARTU"
    PHONE = "TELEPON"
    EMAIL = "EMAIL"
    PERSON_NAME = "ORANG"
    ADDRESS = "ALAMAT"
    PLAT_NOMOR = "PLAT"
    DATE_OF_BIRTH = "TANGGAL_LAHIR"
    EMPLOYER = "INSTANSI"


class PIIEntity(BaseModel):
    entity_type: EntityType
    start: int
    end: int
    raw_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    detector: str  # "rule" | "ner"


class DetectionResult(BaseModel):
    entities: list[PIIEntity]
    min_confidence: float
    below_floor: bool  # F2.7: true -> route to human review before any model sees it


class TokenSpan(BaseModel):
    token: str          # e.g. "[ORANG_1]"
    entity_type: EntityType
    start: int
    end: int


class PseudonymizationResult(BaseModel):
    tokenized_text: str
    tokens: list[TokenSpan]
    subject_id: str


# --- Complaint / triage lifecycle ---

class ComplaintStatus(str, Enum):
    INGESTED = "ingested"
    DETECTING = "detecting"
    DETECTION_FAILED_CLOSED = "detection_failed_closed"
    PENDING_DETECTION_REVIEW = "pending_detection_review"
    TOKENIZED = "tokenized"
    INPUT_BLOCKED = "input_blocked"
    LOCAL_INFERRED = "local_inferred"
    ESCALATED = "escalated"
    OUTPUT_BLOCKED = "output_blocked"
    PENDING_REVIEW = "pending_review"
    REVIEWED_ACCEPTED = "reviewed_accepted"
    REVIEWED_EDITED = "reviewed_edited"
    REVIEWED_REJECTED = "reviewed_rejected"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InferenceTier(str, Enum):
    LOCAL = "local"
    ESCALATION = "escalation"


class TriageOutput(BaseModel):
    """Structured output schema a model must conform to (F4.3)."""
    category: str
    severity: Severity
    summary: str
    draft_response: str
    multi_issue: bool
    field_confidence: dict[str, float]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    tier_used: InferenceTier


class ComplaintRecord(BaseModel):
    job_id: str
    status: ComplaintStatus
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    subject_id: Optional[str] = None
    tokenized_text: Optional[str] = None
    detection: Optional[DetectionResult] = None
    triage: Optional[TriageOutput] = None
    escalation_reason: Optional[str] = None
    guardrail_flags: list[str] = Field(default_factory=list)


# --- Review queue (F9) ---

class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"


class ReviewItem(BaseModel):
    job_id: str
    reason: str  # "low_confidence" | "guardrail" | "detection_uncertain"
    enqueued_at: datetime = Field(default_factory=utcnow)


class ReviewSubmission(BaseModel):
    decision: ReviewDecision
    edited_output: Optional[TriageOutput] = None
    analyst_id: str
    justification: Optional[str] = None


# --- Re-identification (F7) ---

class ReidentifyRequest(BaseModel):
    job_id: str
    fields: Optional[list[EntityType]] = None  # None = all; else partial re-id (F7.5)
    justification: str


class ReidentifyResponse(BaseModel):
    job_id: str
    reidentified_text: str
    fields_resolved: list[EntityType]


# --- Audit (F8) ---

class AuditEvent(BaseModel):
    event_id: str
    event_type: str
    actor: str
    subject_id: Optional[str] = None
    job_id: Optional[str] = None
    justification: Optional[str] = None
    detail: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utcnow)
    region: str = "ap-southeast-3"
