from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AuditLog, Flag, LoanDecision, ReportDraft, ReportStatus, Role, Transaction, User
from app.schemas import DashboardSummaryOut, FlagsByStatus


def _today_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def build_dashboard_summary(db: Session, user: User) -> DashboardSummaryOut:
    by_status = FlagsByStatus()
    for status_value, count in db.query(Flag.status, func.count(Flag.id)).group_by(Flag.status).all():
        setattr(by_status, status_value.value, count)

    summary = DashboardSummaryOut(role=user.role, flags_by_status=by_status)
    today_start = _today_start()

    if user.role == Role.compliance_officer:
        summary.open_flags_count = by_status.open
        summary.escalated_count = by_status.escalated
        summary.transactions_ingested_today = (
            db.query(func.count(Transaction.id)).filter(Transaction.timestamp >= today_start).scalar() or 0
        )
        summary.pending_report_drafts_count = (
            db.query(func.count(ReportDraft.id)).filter(ReportDraft.status == ReportStatus.draft).scalar() or 0
        )
        summary.recent_audit = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(5).all()

    elif user.role == Role.loan_officer:
        week_ago = datetime.utcnow() - timedelta(days=7)
        summary.recent_decisions_count = (
            db.query(func.count(LoanDecision.id))
            .filter(LoanDecision.decided_by == user.id, LoanDecision.timestamp >= week_ago)
            .scalar()
            or 0
        )
        summary.recent_decisions = (
            db.query(LoanDecision)
            .filter(LoanDecision.decided_by == user.id)
            .order_by(LoanDecision.timestamp.desc())
            .limit(5)
            .all()
        )

    elif user.role == Role.auditor:
        summary.total_audit_entries = db.query(func.count(AuditLog.id)).scalar() or 0
        summary.actions_today = (
            db.query(func.count(AuditLog.id)).filter(AuditLog.timestamp >= today_start).scalar() or 0
        )

    return summary
