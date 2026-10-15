"""Labelled eval logs for the CI triage agent.

The same 8 synthetic failing logs + 1 unrelated log used by the
DataPulse analyzer eval (backend/ci_evals.py in kamjula/datapulse),
vendored so this repo is self-contained. The logs are synthetic and
labelled as such; the point is a reproducible retrieval check, one
case per runbook pattern.
"""

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
