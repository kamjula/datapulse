"""Tests for the LangGraph CI triage agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import run_triage  # noqa: E402
from eval_cases import CASES, UNRELATED_LOG  # noqa: E402


def test_all_eval_cases_categorised_and_verified():
    for expected, log in CASES:
        final = run_triage(log)
        assert final["result"]["status"] == "ok"
        assert final["result"]["category"] == expected
        assert final["verified"] is True
        assert final["report"]


def test_unrelated_log_abstains_with_complete_trace():
    final = run_triage(UNRELATED_LOG)
    assert final["result"]["status"] == "abstain"
    nodes = [s["node"] for s in final["trace"]]
    for required in ("collect", "extract", "diagnose", "verify", "report"):
        assert required in nodes


def test_diff_retry_edge_fires_when_first_pass_abstains():
    # No signal in the log and no diff: single attempt. With a diff,
    # the conditional edge must loop back for a second attempt.
    diff = "+++ b/Dockerfile\n@@ -1,3 +1,3 @@\n-FROM python:3.11\n+FROM python:3.12\n"
    final = run_triage(UNRELATED_LOG, diff_text=diff)
    nodes = [s["node"] for s in final["trace"]]
    assert "retry" in nodes
    assert final["attempts"] == 2
