import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, Enum, Text, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


def gen_uuid():
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    loan_officer = "loan_officer"
    compliance_officer = "compliance_officer"
    auditor = "auditor"


class FlagStatus(str, enum.Enum):
    open = "open"
    accepted = "accepted"
    rejected = "rejected"
    escalated = "escalated"


class ReportStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False)
    auth_provider_id = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    pseudonymized_id = Column(String, unique=True, nullable=False)
    risk_profile = Column(String, default="standard")
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="customer")


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_ref = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    source_file = Column(String, nullable=False)

    customer = relationship("Customer", back_populates="transactions")


class Flag(Base):
    __tablename__ = "flags"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    transaction_ref = Column(UUID(as_uuid=False), ForeignKey("transactions.id"), nullable=False)
    rule_triggered = Column(String, nullable=False)
    agent_rationale = Column(Text, nullable=True)
    reviewer_verdict = Column(String, nullable=True)
    status = Column(Enum(FlagStatus), default=FlagStatus.open, nullable=False)
    decided_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)


class LoanDecision(Base):
    __tablename__ = "loan_decisions"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    customer_ref = Column(UUID(as_uuid=False), ForeignKey("customers.id"), nullable=False)
    committee_notes = Column(Text, nullable=False)
    decision = Column(String, nullable=False)
    decided_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class ReportDraft(Base):
    __tablename__ = "report_drafts"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    period = Column(String, nullable=False)
    sections = Column(JSON, nullable=False)
    status = Column(Enum(ReportStatus), default=ReportStatus.draft, nullable=False)
    generated_by = Column(String, nullable=False)
    approved_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Append-only. No route or service method updates/deletes rows here.
    A DB trigger (see init_db.py) additionally rejects UPDATE/DELETE at the
    database level so the guarantee doesn't depend solely on API discipline.
    """
    __tablename__ = "audit_log"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity_ref = Column(String, nullable=True)
    rationale = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
