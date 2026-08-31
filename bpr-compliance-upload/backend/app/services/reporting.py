"""Report-drafting service. Facts are pulled through the FastMCP read-only
tool boundary (app/mcp_server.py) rather than a raw DB session, so the
report-drafting agent has the same no-write, tool-mediated access as the
rest of the agent layer (FR-9: every generated figure links back to a
source-record fetch, not an ad hoc query the agent could shape itself).
"""
from fastmcp import Client
from sqlalchemy.orm import Session

from app.agents.graph import run_report_agent
from app.mcp_server import mcp
from app.models import LoanDecision, ReportDraft
from sqlalchemy import func


async def _fetch_period_facts(period: str) -> dict:
    async with Client(mcp) as client:
        summary_result = await client.call_tool("get_period_summary", {"period": period})
    summary = summary_result.data
    return {
        "aml_screening_summary": {
            "transactions_screened": summary["transaction_count"],
            "total_amount": summary["transaction_total_amount"],
        },
        "loan_committee_activity": {
            "decisions_logged": summary["loan_decision_count"],
        },
    }


async def generate_report_draft(db: Session, period: str, generated_by: str) -> ReportDraft:
    facts = await _fetch_period_facts(period)
    sections = run_report_agent(period, facts)
    draft = ReportDraft(period=period, sections=sections, generated_by=generated_by)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
