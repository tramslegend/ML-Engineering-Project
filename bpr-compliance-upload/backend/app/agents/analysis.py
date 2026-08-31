"""Compliance Analysis agent layer: LangGraph orchestrating a LangChain SQL
Agent and LangChain's Python execution tool, in addition to the mock/real
complete() boundary the rest of the agent layer uses (app/agents/llm.py).

Unlike screening/reporting, the SQL path *generates and executes its own*
SQL -- that's the whole point of "LangChain SQL Agent" as a component -- so
it needs a real tool-calling ChatModel, not the plain string-in/string-out
complete() function. This module therefore only works when
BPR_USE_MOCK_LLM=false (see run_analysis's guard); there is no meaningful
mock path for tool-calling agents.

The Python side intentionally does NOT wrap LangChain's PythonAstREPLTool in
a full ReAct AgentExecutor (i.e. NOT langchain_experimental's
create_pandas_dataframe_agent). That was the original design, and live
testing showed it was unreliable in exactly the way a sibling project's
chart-rendering code (D:\\fastapi_all\\bpp\\bpp-app, agentic_gemini.py)
already learned from and worked around: a ReAct loop given an open-ended
"analyze this" task tends to spend its steps on exploration (checking
columns, re-deriving the row count, second-guessing itself) rather than
computing the answer, then hits max_iterations with nothing to show for it.
bpp's fix for its fixed report charts was to skip the agent entirely and
exec() pre-written code. This module's questions are open-ended (not a fixed
report), so the code can't be pre-written, but the same principle applies in
a weaker form: _run_python_once asks the LLM for exactly ONE pandas
expression, executes it exactly once via PythonAstREPLTool (LangChain's
underlying Python-execution primitive), and retries at most once with the
real error fed back if it fails. No iteration budget, no exploratory
looping -- see _run_python_once's docstring.

Safety scoping: the PRD's "agents get no write access to core banking data"
invariant can't be enforced here by *removing* DB/code access (that would
defeat the point of a SQL/Python agent), so it's enforced by *scoping*
access instead:
  - SQL Agent: connects as the bpr_analyst_ro Postgres role (SELECT-only,
    provisioned in init_db.py, no grant on `users`) instead of the app's
    read-write credential -- bypasses the FastMCP tool boundary used
    elsewhere (a SQL agent needs a real SQLDatabase connection to build and
    run its own queries) but keeps the same no-write, no-auth-data floor.
  - Python execution: never gets a DB session, network, or filesystem tool --
    only a pandas DataFrame already fetched read-only via the same
    bpr_analyst_ro role. It still executes arbitrary LLM-authored Python via
    LangChain's PythonAstREPLTool -- this is a real, acknowledged risk, not a
    solved one, so the /analysis endpoint is RBAC-gated (compliance_officer/
    auditor only) and every query is written to the append-only audit log.
"""
import re
from typing import Optional, TypedDict

import pandas as pd
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain_experimental.tools import PythonAstREPLTool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph
from sqlalchemy import create_engine, text

from app.agents.llm import active_api_key, build_chat_llm, complete, strip_thoughts
from app.config import settings

_ANALYSIS_TABLES = ["customers", "transactions", "flags", "loan_decisions", "report_drafts", "audit_log"]


def _checkpoint_dsn() -> str:
    """psycopg v3 (what langgraph-checkpoint-postgres uses) doesn't understand
    SQLAlchemy's "+psycopg2" driver suffix, so strip it. Uses the app's normal
    read-write credential, NOT bpr_analyst_ro -- conversation memory is
    infrastructure the backend owns, not LLM-generated SQL, so it doesn't need
    (or want) the read-only scoping applied to the SQL/Python agent paths."""
    return settings.database_url.replace("postgresql+psycopg2://", "postgresql://")


def _format_history(history: list[dict], limit: int = 4) -> str:
    """Renders the last `limit` turns as Q/A pairs so the SQL agent, Python
    execution, and synthesis prompts can resolve follow-up references
    ("break that down by month") against what was actually asked and
    answered before -- without this, every question is stateless."""
    if not history:
        return ""
    recent = history[-limit:]
    turns = "\n\n".join(f"Q: {h['question']}\nA: {h['answer']}" for h in recent)
    return f"Conversation so far (most recent last):\n{turns}\n\n"


def _chat_llm():
    return build_chat_llm(temperature=0)


def _build_sql_agent():
    db = SQLDatabase.from_uri(
        settings.analysis_database_url,
        include_tables=_ANALYSIS_TABLES,
        sample_rows_in_table_info=2,
    )
    toolkit = SQLDatabaseToolkit(db=db, llm=_chat_llm())
    return create_sql_agent(llm=_chat_llm(), toolkit=toolkit, agent_type="openai-tools", verbose=False)


def _load_compliance_dataframe() -> pd.DataFrame:
    """Read-only pull (via bpr_analyst_ro) of a joined transactions+flags
    snapshot for the Python side to compute over -- it never gets a DB
    session or connection string itself, only this already-materialized
    DataFrame."""
    engine = create_engine(settings.analysis_database_url)
    query = text(
        """
        SELECT t.id AS transaction_id, t.amount, t.type, t.timestamp,
               c.pseudonymized_id, c.risk_profile,
               f.rule_triggered, f.status AS flag_status
        FROM transactions t
        JOIN customers c ON c.id = t.customer_ref
        LEFT JOIN flags f ON f.transaction_ref = t.id
        ORDER BY t.timestamp DESC
        LIMIT 2000
        """
    )
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


_ERROR_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(Error|Exception)\b")
_NO_MATCHING_COLUMN = "NO_MATCHING_COLUMN"


def _coerce_categorical(value) -> Optional[list[dict]]:
    """label/value pairs -- shared by bar, pie, line, and word-cloud charts,
    which all just differ in how the frontend renders the same shape."""
    try:
        if isinstance(value, pd.Series):
            pairs = list(value.items())[:15]
        elif isinstance(value, pd.DataFrame) and value.shape[1] >= 2:
            pairs = list(zip(value.iloc[:, 0], value.iloc[:, 1]))[:15]
        else:
            return None
        return [{"label": str(k), "value": float(v)} for k, v in pairs]
    except (TypeError, ValueError):
        return None


def _coerce_matrix(value) -> Optional[list[dict]]:
    """row/col/value triples -- shared by heatmap, stacked/grouped bar, and
    Sankey, which are all fundamentally the same "two categories cross a
    numeric value" data, just rendered differently. Accepts either a Series
    with a 2-level MultiIndex (the natural result of df.groupby([a, b]).size())
    or a DataFrame whose first 3 columns are (row, col, value)."""
    try:
        if isinstance(value, pd.Series) and isinstance(value.index, pd.MultiIndex) and value.index.nlevels >= 2:
            frame = value.reset_index().iloc[:, :3]
        elif isinstance(value, pd.DataFrame) and value.shape[1] >= 3:
            frame = value.iloc[:, :3]
        else:
            return None
        frame.columns = ["row", "col", "value"]
        records = frame.head(300).to_dict("records")
        return [{"row": str(r["row"]), "col": str(r["col"]), "value": float(r["value"])} for r in records]
    except (TypeError, ValueError, KeyError):
        return None


def _coerce_xy(value) -> Optional[list[dict]]:
    """x/y numeric pairs for a scatter plot -- the one chart kind here that
    isn't "category + value" or "two categories + value"; it needs two
    independent numeric measures (e.g. amount vs. transaction count)."""
    try:
        if isinstance(value, pd.DataFrame) and value.shape[1] >= 2:
            xs, ys = value.iloc[:, 0], value.iloc[:, 1]
        else:
            return None
        pairs = list(zip(xs, ys))[:300]
        return [{"x": float(px), "y": float(py)} for px, py in pairs]
    except (TypeError, ValueError):
        return None


class _ChartKind:
    """A visualization type's data contract: the shape the generated pandas
    code must produce and how to turn a pandas result into that shape. Adding
    a new chart type is one entry here (plus a frontend renderer) -- nothing
    else in the pipeline needs to change."""

    def __init__(self, key: str, label: str, shape_instructions: str, coerce):
        self.key = key
        self.label = label
        self.shape_instructions = shape_instructions
        self.coerce = coerce


_CATEGORICAL_SHAPE = (
    "Write ONE line of Python assigning to `result` a pandas Series, or a 2-column "
    "DataFrame (category, numeric value), that answers the question below."
)
_MATRIX_SHAPE = (
    "Write ONE line of Python assigning to `result` a pandas Series with a 2-level "
    "MultiIndex in long format (e.g. df.groupby(['row_col', 'col_col']).size() or .sum() -- "
    "do NOT call .unstack() or .pivot(), which produce a wide table with the wrong shape), "
    "or alternatively a long-format DataFrame with exactly 3 columns (row category, column "
    "category, numeric value), that answers the question below."
)
_XY_SHAPE = (
    "Write ONE line of Python assigning to `result` a DataFrame with exactly 2 numeric "
    "columns (an x measure and a y measure -- e.g. df[['amount', 'some_other_numeric_col']], "
    "or an aggregated DataFrame with two numeric columns) that answers the question below."
)

_CHART_KINDS: dict[str, _ChartKind] = {
    "bar": _ChartKind("bar", "bar chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "pie": _ChartKind("pie", "pie chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "line": _ChartKind("line", "line chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "area": _ChartKind("area", "area chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "radar": _ChartKind("radar", "radar chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "radialbar": _ChartKind("radialbar", "radial bar chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "treemap": _ChartKind("treemap", "treemap", _CATEGORICAL_SHAPE, _coerce_categorical),
    "funnel": _ChartKind("funnel", "funnel chart", _CATEGORICAL_SHAPE, _coerce_categorical),
    "wordcloud": _ChartKind("wordcloud", "word cloud", _CATEGORICAL_SHAPE, _coerce_categorical),
    "heatmap": _ChartKind("heatmap", "heatmap", _MATRIX_SHAPE, _coerce_matrix),
    "stackedbar": _ChartKind("stackedbar", "stacked bar chart", _MATRIX_SHAPE, _coerce_matrix),
    "sankey": _ChartKind("sankey", "Sankey diagram", _MATRIX_SHAPE, _coerce_matrix),
    "scatter": _ChartKind("scatter", "scatter plot", _XY_SHAPE, _coerce_xy),
}

# Checked in order -- more specific phrases (e.g. "line chart") before the
# generic ones ("chart") that trigger _is_chart_request but not a specific kind.
_CHART_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("heat map", "heatmap"),
    ("heatmap", "heatmap"),
    ("word cloud", "wordcloud"),
    ("wordcloud", "wordcloud"),
    ("tree map", "treemap"),
    ("treemap", "treemap"),
    ("funnel", "funnel"),
    ("sankey", "sankey"),
    ("flow diagram", "sankey"),
    ("scatter", "scatter"),
    ("stacked bar", "stackedbar"),
    ("grouped bar", "stackedbar"),
    ("radial bar", "radialbar"),
    ("radialbar", "radialbar"),
    ("gauge", "radialbar"),
    ("radar", "radar"),
    ("spider chart", "radar"),
    ("pie", "pie"),
    ("area chart", "area"),
    ("area graph", "area"),
    ("line chart", "line"),
    ("line graph", "line"),
    ("trend line", "line"),
]
_GENERIC_CHART_KEYWORDS = ("chart", "graph", "plot", "visuali")


def _is_chart_request(question: str) -> bool:
    q = question.lower()
    if any(kw in q for kw, _ in _CHART_TYPE_KEYWORDS):
        return True
    return any(k in q for k in _GENERIC_CHART_KEYWORDS)


def _detect_chart_kind(question: str) -> _ChartKind:
    q = question.lower()
    for keyword, kind_key in _CHART_TYPE_KEYWORDS:
        if keyword in q:
            return _CHART_KINDS[kind_key]
    return _CHART_KINDS["bar"]


def _run_python_once(
    question: str, df: pd.DataFrame, chart_kind: Optional[_ChartKind]
) -> tuple[str, Optional[list[dict]]]:
    """One LLM call writes exactly one pandas expression; one PythonAstREPLTool
    call executes it. No ReAct loop, so there is no iteration budget to
    exhaust and no exploratory looping -- see this module's docstring for why."""
    llm = _chat_llm()
    tool = PythonAstREPLTool(locals={"df": df, "pd": pd})
    columns_info = df.dtypes.to_string()

    if chart_kind:
        task = (
            f"{chart_kind.shape_instructions} Respond with ONLY that one line -- no "
            "explanation, no markdown fences, and `result` must not be a plot/Axes "
            "object (e.g. do not call .plot()) -- only a Series or DataFrame.\n\n"
            "If nothing in the columns matches what's specifically asked (e.g. a 'risk "
            "score' or 'compliance score' column that doesn't exist), do NOT substitute a "
            "different, superficially-related metric (e.g. do not chart transaction amounts "
            "just because a 'score' isn't available) -- respond with exactly: "
            f'result = "{_NO_MATCHING_COLUMN}"'
        )
    else:
        task = (
            "Write ONE line of Python assigning to `result` whatever statistic or "
            "aggregate is useful for the question below. Respond with ONLY that one "
            "line -- no explanation, no markdown fences.\n\n"
            "If the question is not answerable from these columns at all (e.g. it asks "
            "about something outside this dataset entirely, like a regulatory definition "
            "or external fact), do not guess or explain in prose -- respond with exactly: "
            f'result = "{_NO_MATCHING_COLUMN}"'
        )

    schema_hint = (
        "Before filtering on any string column (e.g. flag_status, type, risk_profile), base "
        "the values you filter on the actual dtype/known values, not an assumed word -- e.g. "
        "flag_status is one of open/accepted/rejected/escalated, never the literal string "
        "'flagged'; a row counts as a flagged transaction simply because rule_triggered is "
        "not null, regardless of flag_status."
    )
    system = (
        f"DataFrame `df` has {len(df)} rows (the full dataset, not a preview). "
        f"Columns and dtypes:\n{columns_info}\n\n{schema_hint}\n\n{task}"
    )

    def _generate(extra_user: str = "") -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": question + extra_user}]
        code = strip_thoughts(llm.invoke(messages).content).strip("`")
        if code.lower().startswith("python\n"):
            code = code[len("python\n"):]
        return code.strip()

    def _execute(code: str) -> tuple[str, bool]:
        tool.locals["result"] = None
        output = tool.run(code)
        is_error = isinstance(output, str) and bool(_ERROR_PATTERN.match(output.strip()))
        return output, is_error

    code = _generate()
    output, is_error = _execute(code)
    result_value = tool.locals.get("result")
    is_no_match = isinstance(result_value, str) and result_value == _NO_MATCHING_COLUMN
    # An empty/wrong-shaped chart result (e.g. a filter value that doesn't actually
    # appear in the data) is not a Python error, so _execute alone won't catch it --
    # treat it as a soft failure worth one retry too, same as a hard error.
    is_bad_shape = bool(chart_kind) and not is_no_match and not chart_kind.coerce(result_value)

    if is_error or is_bad_shape:
        hint = output if is_error else (
            "the result was not usable -- it was empty, in the wrong shape "
            f"({chart_kind.shape_instructions if chart_kind else 'a Series or DataFrame'} was "
            "required), or used a filter value that doesn't actually appear in the data. "
            "Re-derive any filter values instead of assuming them. If no column actually "
            f'matches what was asked, use result = "{_NO_MATCHING_COLUMN}" rather than '
            "substituting a different metric."
        )
        code = _generate(f"\n\nYour first attempt (`{code}`) did not work: {hint}. Write a corrected single line.")
        output, is_error = _execute(code)
        result_value = tool.locals.get("result")
        is_no_match = isinstance(result_value, str) and result_value == _NO_MATCHING_COLUMN

    if is_no_match:
        return _NO_MATCHING_COLUMN, None
    if is_error:
        return f"Could not compute a result -- last error: {output}", None

    detail = f"```python\n{code}\n```\nResult:\n{result_value}"
    return (detail, chart_kind.coerce(result_value)) if chart_kind else (detail, None)


def _build_research_tools() -> list:
    """Wikipedia and ArXiv need no key; Tavily web search only appears if a
    key is configured. This is the one place in the whole agent layer that
    reaches beyond the bank's own database -- see this module's docstring and
    _needs_research for why it's gated as a fallback, not a first resort."""
    from langchain_community.tools import ArxivQueryRun, WikipediaQueryRun
    from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper

    tools = [
        WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=1500)),
        ArxivQueryRun(api_wrapper=ArxivAPIWrapper(top_k_results=2, doc_content_chars_max=1500)),
    ]
    if settings.tavily_api_key:
        import os

        from langchain_community.tools.tavily_search import TavilySearchResults

        os.environ.setdefault("TAVILY_API_KEY", settings.tavily_api_key)
        tools.append(TavilySearchResults(max_results=4))
    return tools


def _needs_research(sql_result: str, python_result: str) -> bool:
    """Fallback trigger: only reach for external tools once the internal
    compliance data has genuinely failed to answer the question -- covers
    both an explicit NO_MATCHING_COLUMN and the case where both results came
    back essentially empty."""
    if _NO_MATCHING_COLUMN in python_result:
        return True
    return not sql_result.strip() and not python_result.strip()


def _research_node(state: "AnalysisState") -> "AnalysisState":
    """Only reached when internal SQL/Python analysis couldn't answer the
    question (see _route_after_analysis) -- looks it up externally instead of
    the model guessing or the user getting a dead end. Sends only the user's
    own question text to these tools, never any database contents."""
    tools = _build_research_tools()
    llm = _chat_llm().bind_tools(tools)
    history_block = _format_history(state.get("history", []))
    response = llm.invoke([
        {
            "role": "system",
            "content": (
                "You are a compliance research assistant. The bank's internal database "
                "could not answer this question, so look it up using the tools available "
                "(web search, Wikipedia, ArXiv) -- call whichever tool(s) are most likely "
                "to have the answer."
            ),
        },
        {"role": "user", "content": f"{history_block}{state['question']}"},
    ])

    tool_map = {t.name: t for t in tools}
    findings = []
    for call in getattr(response, "tool_calls", None) or []:
        tool = tool_map.get(call["name"])
        if not tool:
            continue
        try:
            result = tool.invoke(call["args"])
        except Exception as exc:  # noqa: BLE001 -- a tool failure is data, not a bug, here
            result = f"(tool error: {exc})"
        findings.append(f"[{call['name']}] {result}")

    state["research_result"] = "\n\n".join(findings) if findings else "No external results found."
    return state


class AnalysisState(TypedDict):
    question: str
    history: list[dict]
    sql_result: str
    python_result: str
    research_result: str
    chart_data: Optional[list[dict]]
    chart_type: Optional[str]
    final_answer: str


def _sql_node(state: AnalysisState) -> AnalysisState:
    agent = _build_sql_agent()
    history_block = _format_history(state.get("history", []))
    prompt = f"{history_block}New question: {state['question']}" if history_block else state["question"]
    result = agent.invoke({"input": prompt})
    state["sql_result"] = strip_thoughts(result.get("output", str(result)))
    return state


def _python_node(state: AnalysisState) -> AnalysisState:
    df = _load_compliance_dataframe()
    history_block = _format_history(state.get("history", []))
    question = f"{history_block}New question: {state['question']}" if history_block else state["question"]
    detail, _ = _run_python_once(question, df, chart_kind=None)
    state["python_result"] = detail
    return state


def _python_chart_node(state: AnalysisState) -> AnalysisState:
    """Visualization requests skip the SQL Agent entirely -- the Python path
    already has the same read-only data loaded as a DataFrame (via
    bpr_analyst_ro), so there is nothing the SQL Agent would add, and asking
    it for a chart type it has no tool to produce was exactly what caused
    both agents to burn through max_iterations without converging."""
    df = _load_compliance_dataframe()
    chart_kind = _detect_chart_kind(state["question"])
    history_block = _format_history(state.get("history", []))
    question = f"{history_block}New question: {state['question']}" if history_block else state["question"]
    detail, chart_data = _run_python_once(question, df, chart_kind)
    state["python_result"] = detail
    state["chart_data"] = chart_data
    state["chart_type"] = chart_kind.key if chart_data else None
    return state


def _synthesize_node(state: AnalysisState) -> AnalysisState:
    history_block = _format_history(state.get("history", []))
    if state.get("chart_data"):
        chart_label = _CHART_KINDS.get(state.get("chart_type"), _CHART_KINDS["bar"]).label
        system = (
            "You are a compliance analyst assistant for an Indonesian rural bank (BPR). "
            f"A {chart_label} has already been generated from the data below (the chart itself "
            "is shown separately in the UI, so do not describe its visual appearance -- colors, "
            f"axes, layout). Respond in markdown with exactly these three sections about the "
            f"{chart_label}, each 1-3 bullet points:\n\n"
            "**What it shows** -- plain-language summary of the pattern, citing the key figures\n"
            "**Insight** -- what stands out, e.g. a concentration, imbalance, or outlier\n"
            "**Conclusion** -- the one takeaway that matters for a compliance officer\n\n"
            "Only state facts present in the chart data below; do not invent numbers or claims "
            "beyond what it shows."
        )
        user = f"{history_block}Question: {state['question']}\n\nChart data: {state['chart_data']}"
    elif state.get("research_result"):
        # Internal data couldn't answer this -- research_result came from web
        # search/Wikipedia/ArXiv instead. Say so plainly; this is general
        # knowledge, not something drawn from the bank's own records.
        system = (
            "You are a compliance analyst assistant for an Indonesian rural bank (BPR). "
            "The bank's internal compliance data did not have this information, so it was "
            "researched externally. Answer the question using ONLY the research findings "
            "below, and make clear this is general/external information, not specific to "
            "this bank's own records. Calibrate length to the question -- concise for a "
            "direct question, structured with markdown bullets if deeper explanation was "
            "asked for."
        )
        user = f"{history_block}Question: {state['question']}\n\nResearch findings: {state['research_result']}"
    elif _NO_MATCHING_COLUMN in state["python_result"]:
        # The generated code itself reported no matching column -- a known,
        # true cause, so let the model explain it plainly.
        system = (
            "You are a compliance analyst assistant for an Indonesian rural bank (BPR). "
            "The requested metric does not exist in the compliance data. In 1-2 sentences, "
            "say plainly that this figure isn't tracked, and name what related data IS "
            "available instead if you can tell from the input. Do not guess at data-quality "
            "problems (missing rows, bad file formats, PDFs, etc.) -- the only reason is that "
            "no matching column exists."
        )
        user = f"{history_block}Question: {state['question']}\n\nPython result: {state['python_result']}"
    elif state["python_result"] and not state["sql_result"]:
        # Chart/analysis was requested but computation failed -- state.python_result
        # holds the real error message here, so summarize it rather than inventing
        # a cause; do not speculate beyond what this actually says.
        system = (
            "You are a compliance analyst assistant for an Indonesian rural bank (BPR). "
            "A chart or analysis was requested but the computation failed. In 1-2 "
            "sentences, state plainly what went wrong, based ONLY on the error message "
            "below -- do not invent causes (data quality, file formats, etc.) beyond what "
            "the error actually says."
        )
        user = f"{history_block}Question: {state['question']}\n\nDetail: {state['python_result']}"
    else:
        system = (
            "You are a compliance analyst assistant for an Indonesian rural bank (BPR). "
            "Combine the SQL lookup result and the statistical/Python analysis result into an "
            "answer for the compliance officer's question below. Only state facts present in "
            "the two inputs; do not invent figures. If this is a follow-up to the conversation "
            "so far, answer it in that context.\n\n"
            "Calibrate length and structure to what was actually asked:\n"
            "- A direct factual question (how many / what is / which / list) gets a direct, "
            "concise answer -- 1-3 sentences, no headers or bullets.\n"
            "- If the question explicitly asks for insight, conclusion, explanation, analysis, "
            "reasoning, trends, or implications, answer thoroughly in markdown with short "
            "labeled sections (e.g. **What the data shows**, **Insight**, **Conclusion**), each "
            "with 1-3 bullet points.\n"
            "Never pad a simple factual question with unnecessary structure, and never compress "
            "a request for deeper analysis into a single terse sentence."
        )
        user = (
            f"{history_block}Question: {state['question']}\n\n"
            f"SQL agent result: {state['sql_result']}\n\n"
            f"Python analysis result: {state['python_result']}"
        )
    state["final_answer"] = complete(system, user)
    state["history"] = state.get("history", []) + [{"question": state["question"], "answer": state["final_answer"]}]
    return state


def _route(state: AnalysisState) -> str:
    return "python_chart" if _is_chart_request(state["question"]) else "sql_lookup"


def _route_after_analysis(state: AnalysisState) -> str:
    return "research" if _needs_research(state["sql_result"], state["python_result"]) else "synthesize"


def build_analysis_graph(checkpointer=None):
    graph = StateGraph(AnalysisState)
    graph.add_node("sql_lookup", _sql_node)
    graph.add_node("python_analysis", _python_node)
    graph.add_node("python_chart", _python_chart_node)
    graph.add_node("research", _research_node)
    graph.add_node("synthesize", _synthesize_node)
    graph.set_conditional_entry_point(_route, {"sql_lookup": "sql_lookup", "python_chart": "python_chart"})
    graph.add_edge("sql_lookup", "python_analysis")
    graph.add_conditional_edges(
        "python_analysis", _route_after_analysis, {"research": "research", "synthesize": "synthesize"}
    )
    graph.add_edge("research", "synthesize")
    graph.add_edge("python_chart", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile(checkpointer=checkpointer)


_checkpoint_tables_ready = False


def run_analysis(question: str, thread_id: str) -> dict:
    if settings.use_mock_llm or not active_api_key():
        raise RuntimeError(
            "Compliance Analysis needs a live LLM -- the SQL Agent and Python execution "
            "require real tool-calling, unlike the deterministic mock used elsewhere. Set "
            "BPR_USE_MOCK_LLM=false and configure BPR_LLM_PROVIDER plus its API key."
        )
    global _checkpoint_tables_ready
    with PostgresSaver.from_conn_string(_checkpoint_dsn()) as checkpointer:
        if not _checkpoint_tables_ready:
            checkpointer.setup()  # idempotent; only worth doing once per process
            _checkpoint_tables_ready = True
        graph = build_analysis_graph(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(
            {
                "question": question,
                "sql_result": "",
                "python_result": "",
                "research_result": "",
                "chart_data": None,
                "chart_type": None,
                "final_answer": "",
            },
            config=config,
        )
    return {
        "question": question,
        "sql_result": result["sql_result"],
        "python_result": result["python_result"],
        "chart_data": result["chart_data"],
        "chart_type": result["chart_type"],
        "final_answer": result["final_answer"],
    }
