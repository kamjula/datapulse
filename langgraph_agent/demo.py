"""Demo: one failing CI log through the LangGraph triage agent.

Prints the final report, then the node-by-node trace the graph
recorded while producing it.  Run: python demo.py
"""
from agent import run_triage
from eval_cases import CASES


def main() -> None:
    expected, log = CASES[0]  # dependency_resolution
    final = run_triage(log)
    print(f"=== log case: {expected} ===\n")
    print(final["report"])
    print("\ngraph trace:")
    for step in final["trace"]:
        print(f"  {step['node']:9s} {step['ms']:6.1f} ms  {step['note']}")


if __name__ == "__main__":
    main()
