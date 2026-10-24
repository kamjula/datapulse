"""CI triage agent built with LangGraph.

The DataPulse CI failure analyzer (ci_analyzer.py, vendored from
github.com/kamjula/datapulse) wrapped in a real LangGraph StateGraph:

    START -> collect -> extract -> diagnose --(retry once)--> diagnose
                                     |
                                     +-> verify -> report -> END

The retry is a conditional edge: if the first diagnosis abstains and
a PR diff is available, the graph loops back into `diagnose` with the
diff included (its file names widen the retrieval query). `verify`
re-reads the cited runbook and checks the suggested cause/fix really
comes from it — a diagnosis that is not grounded in its citation does
not ship. Every node appends to a trace in the graph state, so a run
can be inspected step by step.

Run it:  python demo.py
Eval it: python evals.py
"""
import operator
import os
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from ci_analyzer import KB_PATH, CIFailureAnalyzer, extract_error_lines

ANALYZER = CIFailureAnalyzer()


class TriageState(TypedDict, total=False):
    log_text: str
    diff_text: str
    use_diff: bool
    error_lines: list
    result: dict
    verified: bool
    attempts: int
    report: str
    trace: Annotated[list, operator.add]


def _step(node: str, note: str, t0: float) -> dict:
    return {"node": node, "note": note,
            "ms": round((time.perf_counter() - t0) * 1000, 1)}


def collect(state: TriageState) -> dict:
    t0 = time.perf_counter()
    n = len([ln for ln in state["log_text"].splitlines() if ln.strip()])
    return {"trace": [_step("collect", f"{n} non-empty log lines in", t0)]}


def extract(state: TriageState) -> dict:
    t0 = time.perf_counter()
    errors = extract_error_lines(state["log_text"])
    return {"error_lines": errors,
            "trace": [_step("extract", f"{len(errors)} error lines found", t0)]}


def diagnose(state: TriageState) -> dict:
    t0 = time.perf_counter()
    diff = state["diff_text"] if state.get("use_diff") else ""
    result = ANALYZER.analyze(state["log_text"], diff)
    attempts = state.get("attempts", 0) + 1
    note = f"{result.get('category', 'abstain')} after attempt {attempts}"
    return {"result": result, "attempts": attempts,
            "trace": [_step("diagnose", note, t0)]}


def route_after_diagnose(state: TriageState) -> str:
    """Retry once with the PR diff if the first pass abstained."""
    if state["result"]["status"] == "abstain" \
            and state.get("attempts", 0) < 2 and state.get("diff_text"):
        return "retry"
    return "verify"


def retry(state: TriageState) -> dict:
    t0 = time.perf_counter()
    return {"use_diff": True,
            "trace": [_step("retry", "retrying with the PR diff included", t0)]}


def verify(state: TriageState) -> dict:
    t0 = time.perf_counter()
    result = state["result"]
    if result["status"] != "ok":
        return {"verified": False,
                "trace": [_step("verify", "nothing to verify (abstained)", t0)]}
    source = result["citations"][0]["source"]
    with open(os.path.join(KB_PATH, source), encoding="utf-8") as fh:
        text = fh.read()
    flat = " ".join(text.split())
    ok = (result["likely_cause"][:60] in flat
          and result["suggested_fix"][:60] in flat)
    return {"verified": ok,
            "trace": [_step("verify", f"cause/fix grounded in {source}: {ok}", t0)]}


def report(state: TriageState) -> dict:
    t0 = time.perf_counter()
    result = state["result"]
    if result["status"] != "ok":
        text = ("Status: abstain\n"
                f"{result['message']}\n"
                f"Attempts: {state.get('attempts', 0)}")
    else:
        cites = ", ".join(c["source"] for c in result["citations"])
        text = (f"Category: {result['category']}\n"
                f"Likely cause: {result['likely_cause']}\n"
                f"Suggested fix: {result['suggested_fix']}\n"
                f"Citations: {cites}\n"
                f"Verified against runbook: {state.get('verified', False)}\n"
                f"Attempts: {state.get('attempts', 0)}")
    return {"report": text,
            "trace": [_step("report", "triage report assembled", t0)]}


def build_graph():
    g = StateGraph(TriageState)
    g.add_node("collect", collect)
    g.add_node("extract", extract)
    g.add_node("diagnose", diagnose)
    g.add_node("retry", retry)
    g.add_node("verify", verify)
    g.add_node("report", report)
    g.add_edge(START, "collect")
    g.add_edge("collect", "extract")
    g.add_edge("extract", "diagnose")
    g.add_conditional_edges("diagnose", route_after_diagnose,
                            {"retry": "retry", "verify": "verify"})
    g.add_edge("retry", "diagnose")
    g.add_edge("verify", "report")
    g.add_edge("report", END)
    return g.compile()


GRAPH = build_graph()


def run_triage(log_text: str, diff_text: str = "") -> dict:
    """Run the graph end to end; return the final state."""
    return GRAPH.invoke({"log_text": log_text, "diff_text": diff_text,
                         "use_diff": False, "attempts": 0, "trace": []})
