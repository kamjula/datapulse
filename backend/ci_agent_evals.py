"""Eval harness for the CI triage agent.

Run:  .venv/bin/python -m backend.ci_agent_evals   (from the project root)

Runs the full agent graph (not just the analyzer) over the same
synthetic logs as backend.ci_evals and checks three things:
  1. end-to-end category accuracy
  2. every successful diagnosis passes the verify node (cause/fix
     grounded in the cited runbook)
  3. the unrelated log still ends in abstention, and every run's trace
     contains all five steps in order
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ci_agent import run_ci_agent, STEPS
from backend.ci_evals import CASES, UNRELATED_LOG


def main() -> int:
    correct = verified = traced = 0
    for expected, log in CASES:
        out = run_ci_agent(log)
        report, trace = out["report"], out["trace"]
        ok = report["status"] == "ok" and report["category"] == expected
        correct += ok
        verified += bool(report["verified"])
        traced += [t["step"] for t in trace] == STEPS
        print(
            f"{'PASS' if ok else 'MISS'}  expected={expected:24s} "
            f"got={report['category'] or 'abstain'}  verified={report['verified']}"
        )
    total = len(CASES)
    out = run_ci_agent(UNRELATED_LOG)
    abstain_ok = out["report"]["status"] == "abstain"
    print(f"abstain on unrelated log: {'PASS' if abstain_ok else 'MISS'}")
    print(f"category accuracy: {correct}/{total} = {correct / total:.2f}")
    print(f"verified diagnoses: {verified}/{total}")
    print(f"complete traces: {traced}/{total}")
    return 0 if correct == total and abstain_ok and verified == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
