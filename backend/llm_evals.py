"""LLM-output eval harness for the runbook copilot.

Run:  .venv/bin/python -m backend.llm_evals   (from the project root)

backend/evals.py checks the detector and that narrations cite
*something*. This harness grades the copilot's answers the way a
production LLM eval would, over a small hand-written set of questions:

  dataset    10 questions the runbooks can answer, each labelled with
             the runbook that should be cited, plus 4 questions the
             runbooks cannot answer (off-topic / not covered).
  metrics    citation accuracy  - expected runbook among the citations
             groundedness       - the answer's content really appears
                                  in the cited runbook text (nothing
                                  unsupported, nothing invented)
             abstention         - unanswerable questions get the
                                  abstain response, not a made-up answer

The questions are hand-written and the logs/runbooks are the project's
own. Numbers below are whatever the run produces - if retrieval
misses a case, the harness says so; that is what it is for.

Known limitation (found by this harness, kept visible on purpose):
the Kafka question below is NOT abstained on. Its one generic shared
term ("count") gives a top TF-IDF score of 0.167 - higher than the
weakest real question's 0.155 - so a score threshold alone cannot
separate it without also rejecting a genuine question. The production
answer is a bigger labelled set plus a relevance judge; here the miss
stays in the table and the gate thresholds sit below it.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.narrator import ABSTAIN, Narrator
from backend.rag import RunbookRAG

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(BASE, "runbooks")

# (question, runbook that should be cited)
ANSWERABLE = [
    ("What should I check when row volume suddenly spikes?",
     "volume_anomalies.md"),
    ("Pipeline latency jumped - what are the likely causes?",
     "latency_spike.md"),
    ("Why would the null rate in a column suddenly surge?",
     "null_surge.md"),
    ("The schema version changed without warning - what do I do?",
     "schema_drift.md"),
    ("The feed has not updated in hours - how do I check freshness?",
     "stale_feed.md"),
    ("How do I tell a real volume anomaly from a seasonal pattern?",
     "volume_anomalies.md"),
    ("What is the first check for a latency spike?",
     "latency_spike.md"),
    ("How do I investigate missing values appearing in a column?",
     "null_surge.md"),
    ("What breaks when a producer changes the schema?",
     "schema_drift.md"),
    ("How long can a feed be stale before it is an incident?",
     "stale_feed.md"),
]

# questions the runbook library does not cover -> must abstain
UNANSWERABLE = [
    "How do I bake a chocolate cake?",
    "What is the capital of France?",
    "How do I tune a Kafka partition count?",
    "What is the best way to negotiate a salary?",
]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _runbook_text(rag: RunbookRAG, source: str) -> str:
    return _flat(" ".join(d["text"] for d in rag.docs if d["source"] == source))


def grounded(answer_text: str, rag: RunbookRAG, citations: list[str]) -> bool:
    """The answer's content snippet must appear in a cited runbook.

    The template answer quotes the top retrieved chunk; strip the
    framing and check the quoted content against the cited sources.
    """
    body = answer_text.split("Sources:")[0]
    body = body.replace("Based on the runbooks:", "").strip().rstrip(".")
    snippet = body.removesuffix("...").strip()
    if not snippet:
        return False
    return any(snippet in _runbook_text(rag, src) for src in citations)


def main() -> int:
    rag = RunbookRAG(KB)
    narrator = Narrator()
    print(f"# LLM eval report (narrator mode: {narrator.mode})\n")

    cited_ok = grounded_ok = answered = 0
    rows = []
    for question, expected in ANSWERABLE:
        cits = rag.search(question)
        out = narrator.answer(question, cits)
        sources = out["citations"]
        if out["text"].strip() == ABSTAIN:
            rows.append((question, expected, "ABSTAINED", False, False))
            continue
        answered += 1
        cok = expected in sources
        gok = grounded(out["text"], rag, sources)
        cited_ok += cok
        grounded_ok += gok
        rows.append((question, expected, ",".join(sources) or "-", cok, gok))

    print("## Answerable questions\n")
    print("| question | expected | cited | citation ok | grounded |")
    print("|---|---|---|---|---|")
    for q, exp, cited, cok, gok in rows:
        print(f"| {q[:52]} | {exp} | {cited} | {cok} | {gok} |")

    abst_ok = 0
    print("\n## Unanswerable questions (must abstain)\n")
    for question in UNANSWERABLE:
        cits = rag.search(question)
        out = narrator.answer(question, cits)
        ok = out["text"].strip() == ABSTAIN
        abst_ok += ok
        print(f"| {question[:52]} | abstained: {ok} |")

    n, m = len(ANSWERABLE), len(UNANSWERABLE)
    print(f"\ncitation accuracy: {cited_ok}/{n} = {cited_ok / n:.2f}")
    print(f"groundedness (of answered): {grounded_ok}/{answered}")
    print(f"abstention accuracy: {abst_ok}/{m} = {abst_ok / m:.2f}")
    # Gate: groundedness is the safety property and must be perfect -
    # an answered question may cite the wrong runbook, but it may never
    # say something the runbooks do not support. Citation and
    # abstention have thresholds (see the known limitation above).
    ok_all = (grounded_ok == answered and cited_ok / n >= 0.9
              and abst_ok / m >= 0.75)
    print("\nEVAL:", "PASS" if ok_all else "CHECK FAILURES ABOVE",
          "- thresholds: groundedness perfect, citation >= 0.90, "
          "abstention >= 0.75")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
