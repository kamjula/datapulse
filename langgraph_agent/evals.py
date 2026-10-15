"""End-to-end eval for the LangGraph CI triage agent.

Runs the compiled graph over the 8 labelled synthetic logs in
eval_cases.py and reports:
  * category accuracy
  * fraction of answered diagnoses that verify against the runbook
    they cite (groundedness)
  * trace completeness (every run visits
    collect/extract/diagnose/verify/report)
  * abstention on the unrelated log

Run: python evals.py
"""
from agent import run_triage
from eval_cases import CASES, UNRELATED_LOG

REQUIRED_NODES = ["collect", "extract", "diagnose", "verify", "report"]


def main() -> int:
    correct = verified = traced = answered = 0
    for expected, log in CASES:
        final = run_triage(log)
        result = final["result"]
        got = result.get("category", "abstain")
        if result["status"] == "ok" and got == expected:
            correct += 1
        if result["status"] == "ok":
            answered += 1
            if final.get("verified"):
                verified += 1
        nodes = [s["node"] for s in final["trace"]]
        if all(n in nodes for n in REQUIRED_NODES):
            traced += 1
        print(f"expected={expected:24s} got={got:24s} "
              f"verified={final.get('verified')} nodes={len(nodes)}")
    noise = run_triage(UNRELATED_LOG)
    abstained = noise["result"]["status"] == "abstain"
    n = len(CASES)
    print()
    print(f"category accuracy: {correct}/{n} = {correct / n:.2f}")
    print(f"verified (of answered): {verified}/{answered}")
    print(f"complete traces: {traced}/{n}")
    print(f"abstention on unrelated log: {'PASS' if abstained else 'FAIL'}")
    ok = correct == n and verified == answered and traced == n and abstained
    print("EVAL:", "PASS" if ok else "CHECK FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
