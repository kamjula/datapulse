"""Demo: analyze one failing CI log and print the suggestion.

Run from the project root:  .venv/bin/python examples/ci_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ci_analyzer import CIFailureAnalyzer

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
    result = CIFailureAnalyzer().analyze(SAMPLE_LOG, SAMPLE_DIFF)
    print("status:  ", result["status"])
    if result["status"] == "ok":
        print("category:", result["category"])
        print("cause:   ", result["likely_cause"])
        print("fix:     ", result["suggested_fix"])
        print("cited:   ", [c["source"] for c in result["citations"]])
    else:
        print(result["message"])
    print("error lines found:", len(result["error_lines"]))
