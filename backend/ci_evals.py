"""Eval harness for the CI failure analyzer.

Run:  .venv/bin/python -m backend.ci_evals   (from the project root)

Feeds the analyzer a small set of hand-written CI logs, one per failure
pattern in ci_runbooks/, plus one unrelated log that should make it
abstain. The logs are synthetic and labelled as such; the point is to
check the retrieval matches the right pattern, reproducibly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ci_analyzer import CIFailureAnalyzer

CASES = [
    (
        "dependency_resolution",
        """\
Run pip install -r requirements.txt
ERROR: Could not find a version that satisfies the requirement pandas==9.9.9
ERROR: No matching distribution found for pandas==9.9.9
""",
    ),
    (
        "test_assertion",
        """\
tests/test_detector.py::test_spike_flagged FAILED
AssertionError: assert 0 == 1
1 failed, 8 passed in 2.31s
""",
    ),
    (
        "timeout",
        """\
The job running on runner-3 has exceeded the maximum execution time of 360 minutes.
##[error]The operation was canceled
""",
    ),
    (
        "out_of_memory",
        """\
Compiling assets...
/bin/sh: line 1: 2214 Killed  python train.py
Cannot allocate memory
""",
    ),
    (
        "lint_format",
        """\
Run black --check .
would reformat src/app.py
1 file would be reformatted, 4 files would be left unchanged.
Error: Process completed with exit code 1.
""",
    ),
    (
        "auth_permission",
        """\
Pushing image to registry...
Error: 403 Forbidden
Resource not accessible by integration
""",
    ),
    (
        "docker_build",
        """\
#12 ERROR: failed to solve: executor failed running [/bin/sh -c pip install -r req.txt]
Dockerfile:14
""",
    ),
    (
        "syntax_import",
        """\
ERROR collecting tests/test_app.py
ModuleNotFoundError: No module named 'requests'
1 error during collection
""",
    ),
]

UNRELATED_LOG = """\
Deploy preview ready at https://preview.example.com
Build finished in 42s. All checks passed.
"""


def main() -> int:
    analyzer = CIFailureAnalyzer()
    correct = 0
    for expected, log in CASES:
        result = analyzer.analyze(log)
        got = result.get("category", "abstain")
        ok = result["status"] == "ok" and got == expected
        correct += ok
        print(f"{'PASS' if ok else 'MISS'}  expected={expected:24s} got={got}")
    total = len(CASES)
    abstain_ok = analyzer.analyze(UNRELATED_LOG)["status"] == "abstain"
    print(f"abstain on unrelated log: {'PASS' if abstain_ok else 'MISS'}")
    print(f"category accuracy: {correct}/{total} = {correct / total:.2f}")
    return 0 if correct == total and abstain_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
