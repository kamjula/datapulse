"""Demo: run the CI triage agent on one failing log and print its report.

Run from the project root:  .venv/bin/python examples/ci_agent_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ci_agent import run_ci_agent

SAMPLE_LOG = """\
Run pytest
tests/test_api.py::test_health FAILED
AssertionError: assert 500 == 200
1 failed, 12 passed in 3.02s
Error: Process completed with exit code 1.
"""

SAMPLE_DIFF = """\
diff --git a/backend/app.py b/backend/app.py
+++ b/backend/app.py
"""

if __name__ == "__main__":
    out = run_ci_agent(SAMPLE_LOG, SAMPLE_DIFF)
    report = out["report"]
    print("status:  ", report["status"])
    print("category:", report["category"])
    print("cause:   ", report["likely_cause"])
    print("fix:     ", report["suggested_fix"])
    print("cited:   ", report["citations"])
    print("attempts:", report["attempts"], "| verified:", report["verified"])
    print("trace:")
    for t in out["trace"]:
        print(f"  {t['step']:9s} {t['note']} ({t['ms']} ms)")
