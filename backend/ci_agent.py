"""CI triage agent: a small state-graph workflow over the CI analyzer.

Nodes run in order: collect -> extract -> diagnose -> verify -> report.
If the first diagnosis abstains and a PR diff is available, the agent
retries once with the diff included (its file names widen the retrieval
query) before giving up. The verify node checks the suggested cause/fix
really comes from the cited runbook, so a diagnosis cannot drift away
from its citation.

Dependency-light on purpose (project rule): the graph is a plain list
of node functions over a shared state dict, not a framework. Every node
appends to state["trace"], so a run can be inspected step by step.
"""
import os
import time

from backend.ci_analyzer import CIFailureAnalyzer, extract_error_lines, KB_PATH

STEPS = ["collect", "extract", "diagnose", "verify", "report"]


def _trace(state: dict, step: str, note: str, t0: float) -> None:
    state["trace"].append(
        {"step": step, "note": note, "ms": round((time.time() - t0) * 1000, 1)}
    )


def _collect(state: dict) -> dict:
    t0 = time.time()
    state["log_lines"] = len(state["log_text"].splitlines())
    _trace(state, "collect", f"{state['log_lines']} log lines in", t0)
    return state


def _extract(state: dict) -> dict:
    t0 = time.time()
    state["error_lines"] = extract_error_lines(state["log_text"])
    _trace(state, "extract", f"{len(state['error_lines'])} error lines found", t0)
    return state


def _diagnose(state: dict) -> dict:
    t0 = time.time()
    analyzer = state["analyzer"]
    result = analyzer.analyze(state["log_text"])
    state["attempts"] = 1
    if result["status"] == "abstain" and state["diff_text"]:
        # one retry, with the PR diff widening the retrieval query
        result = analyzer.analyze(state["log_text"], state["diff_text"])
        state["attempts"] = 2
    state["result"] = result
    note = result.get("category", "abstain")
    _trace(state, "diagnose", f"{note} after {state['attempts']} attempt(s)", t0)
    return state


def _verify(state: dict) -> dict:
    t0 = time.time()
    result = state["result"]
    if result["status"] != "ok":
        state["verified"] = False
        _trace(state, "verify", "nothing to verify (abstained)", t0)
        return state
    source = result["citations"][0]["source"]
    with open(os.path.join(KB_PATH, source), encoding="utf-8") as fh:
        text = fh.read()
    flat = " ".join(text.split())
    state["verified"] = (
        result["likely_cause"][:60] in flat and result["suggested_fix"][:60] in flat
    )
    _trace(state, "verify", f"cause/fix grounded in {source}: {state['verified']}", t0)
    return state


def _report(state: dict) -> dict:
    t0 = time.time()
    result = state["result"]
    state["report"] = {
        "status": result["status"],
        "category": result.get("category"),
        "likely_cause": result.get("likely_cause", ""),
        "suggested_fix": result.get("suggested_fix", ""),
        "citations": [c["source"] for c in result.get("citations", [])],
        "attempts": state["attempts"],
        "verified": state["verified"],
        "error_lines": result.get("error_lines", []),
    }
    _trace(state, "report", "triage report assembled", t0)
    return state


NODES = [_collect, _extract, _diagnose, _verify, _report]


def run_ci_agent(log_text: str, diff_text: str = "") -> dict:
    """Run the triage graph over one CI log; returns report + trace."""
    state = {
        "log_text": log_text,
        "diff_text": diff_text,
        "analyzer": CIFailureAnalyzer(),
        "trace": [],
        "attempts": 0,
        "verified": False,
    }
    for node in NODES:
        state = node(state)
    return {"report": state["report"], "trace": state["trace"]}
