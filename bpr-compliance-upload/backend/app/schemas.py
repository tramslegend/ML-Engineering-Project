from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.models import FlagStatus, ReportStatus, Role


class LoginRequest(BaseModel):
    auth_provider_id: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    name: str


class CustomerOut(BaseModel):
    id: str
    pseudonymized_id: str
    risk_profile: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionOut(BaseModel):
    id: str
    customer_ref: str
    amount: float
    type: str
    timestamp: datetime
    source_file: str

    class Config:
        from_attributes = True


class FlagOut(BaseModel):
    id: str
    transaction_ref: str
    rule_triggered: str
    agent_rationale: Optional[str]
    reviewer_verdict: Optional[str]
    status: FlagStatus
    decided_by: Optional[str]
    created_at: datetime
    decided_at: Optional[datetime]

    class Config:
        from_attributes = True


class FlagDecisionRequest(BaseModel):
    decision: str  # "accepted" | "rejected" | "escalated"
    note: Optional[str] = None


class LoanDecisionCreate(BaseModel):
    customer_ref: str
    committee_notes: str
    decision: str


class LoanDecisionOut(BaseModel):
    id: str
    customer_ref: str
    committee_notes: str
    decision: str
    decided_by: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ReportDraftRequest(BaseModel):
    period: str  # e.g. "2026-08"


class ReportDraftOut(BaseModel):
    id: str
    period: str
    sections: dict[str, Any]
    status: ReportStatus
    generated_by: str
    approved_by: Optional[str]
    created_at: datetime
    approved_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: str
    actor: str
    action: str
    entity_ref: Optional[str]
    rationale: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class CustomerHistoryOut(BaseModel):
    customer_ref: str
    pseudonymized_id: str
    risk_profile: str
    transactions: list[TransactionOut]
    flags: list[FlagOut]


class FlagsByStatus(BaseModel):
    open: int = 0
    accepted: int = 0
    rejected: int = 0
    escalated: int = 0


class DashboardSummaryOut(BaseModel):
    role: Role
    flags_by_status: FlagsByStatus = FlagsByStatus()

    # compliance_officer
    open_flags_count: int = 0
    escalated_count: int = 0
    transactions_ingested_today: int = 0
    pending_report_drafts_count: int = 0
    recent_audit: list[AuditLogOut] = []

    # loan_officer
    recent_decisions_count: int = 0
    recent_decisions: list[LoanDecisionOut] = []

    # auditor
    total_audit_entries: int = 0
    actions_today: int = 0


class AnalysisRequest(BaseModel):
    question: str
    thread_id: str


class ChartDataPoint(BaseModel):
    """Categorical charts (bar/pie/line/area/radar/radialbar/treemap/funnel/
    wordcloud) use label+value; heatmap/stackedbar/sankey use row+col+value;
    scatter uses x+y. One model covers all three shapes since only the fields
    a given chart kind actually needs are populated."""

    label: Optional[str] = None
    row: Optional[str] = None
    col: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    value: Optional[float] = None


class AnalysisResponse(BaseModel):
    question: str
    sql_result: str
    python_result: str
    chart_data: Optional[list[ChartDataPoint]] = None
    chart_type: Optional[str] = None
    final_answer: str
