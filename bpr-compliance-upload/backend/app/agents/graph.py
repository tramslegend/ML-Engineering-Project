"""LangGraph agent layer: screening agent -> reviewer agent (FR-5, FR-6),
and a separate report-drafting agent (FR-8, FR-9).

The screening/reviewer graph never touches the database directly — it is
handed already-computed rule results (app/services/screening.py) and asked
only to (a) explain them in plain language and (b) sanity-check that the
explanation is actually consistent with the triggered rule, mirroring the
"reviewer cross-checks the first agent before it reaches a human" requirement.
Any DB reads the report-drafting agent needs go through the read-only
FastMCP boundary in app/mcp_server.py, never a raw session.
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents.llm import complete
from app.services.screening import ScreeningResult


class ScreeningState(TypedDict):
    transaction_summary: str
    rule_results: list[str]
    rationale: str
    reviewer_verdict: str


def _screen_node(state: ScreeningState) -> ScreeningState:
    system = (
        "You are a compliance screening assistant for an Indonesian rural bank (BPR). "
        "Given a flagged transaction and the rule(s) it triggered, write one concise, "
        "plain-language sentence explaining why this looks like it deserves human review. "
        "Do not invent facts not present in the input."
    )
    user = (
        f"Transaction: {state['transaction_summary']}\n"
        f"Rule(s) triggered: {', '.join(state['rule_results'])}"
    )
    state["rationale"] = complete(system, user)
    return state


def _review_node(state: ScreeningState) -> ScreeningState:
    # Reviewer cross-checks the rationale actually references a rule that was
    # really triggered (FR-6) — a second, independent guard before this ever
    # reaches a human compliance officer, catching the case where the first
    # agent hallucinates a rule that wasn't in rule_results.
    rationale_lower = state["rationale"].lower()
    mentions_a_real_rule = any(rule.replace("_", " ") in rationale_lower or rule in rationale_lower for rule in state["rule_results"])
    if mentions_a_real_rule or not state["rule_results"]:
        state["reviewer_verdict"] = "consistent"
    else:
        state["reviewer_verdict"] = "inconsistent: rationale does not reference a triggered rule"
    return state


def build_screening_graph():
    graph = StateGraph(ScreeningState)
    graph.add_node("screen", _screen_node)
    graph.add_node("review", _review_node)
    graph.set_entry_point("screen")
    graph.add_edge("screen", "review")
    graph.add_edge("review", END)
    return graph.compile()


_screening_graph = build_screening_graph()


def run_screening_agent(transaction_summary: str, rule_results: list[ScreeningResult]) -> tuple[str, str]:
    """Returns (agent_rationale, reviewer_verdict)."""
    result = _screening_graph.invoke({
        "transaction_summary": transaction_summary,
        "rule_results": [r.rule_triggered for r in rule_results],
        "rationale": "",
        "reviewer_verdict": "",
    })
    return result["rationale"], result["reviewer_verdict"]


class ReportState(TypedDict):
    period: str
    facts: dict
    sections: dict


def _draft_node(state: ReportState) -> ReportState:
    system = (
        "You are drafting a section of a monthly LBBPR-style regulatory compliance report "
        "for OJK. Use only the figures provided; every claim must be traceable to the input facts. "
        "Write 2-4 sentences."
    )
    facts = state["facts"]
    sections = {}
    for section_name, section_facts in facts.items():
        user = f"Period: {state['period']}\nSection: {section_name}\nFacts: {section_facts}"
        sections[section_name] = {
            "narrative": complete(system, user),
            "source_facts": section_facts,
        }
    state["sections"] = sections
    return state


def build_report_graph():
    graph = StateGraph(ReportState)
    graph.add_node("draft", _draft_node)
    graph.set_entry_point("draft")
    graph.add_edge("draft", END)
    return graph.compile()


_report_graph = build_report_graph()


def run_report_agent(period: str, facts: dict) -> dict:
    result = _report_graph.invoke({"period": period, "facts": facts, "sections": {}})
    return result["sections"]
