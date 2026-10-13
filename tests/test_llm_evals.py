"""Tests for the LLM-output eval harness (backend/llm_evals.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm_evals import ANSWERABLE, KB, UNANSWERABLE, grounded
from backend.narrator import ABSTAIN, Narrator
from backend.rag import RunbookRAG


def test_dataset_labels_point_at_real_runbooks():
    rag = RunbookRAG(KB)
    sources = {d["source"] for d in rag.docs}
    for _, expected in ANSWERABLE:
        assert expected in sources
    assert len(ANSWERABLE) >= 8 and len(UNANSWERABLE) >= 3


def test_grounded_check_accepts_real_answer_and_rejects_invented_one():
    rag = RunbookRAG(KB)
    narrator = Narrator()
    question, _ = ANSWERABLE[0]
    out = narrator.answer(question, rag.search(question))
    assert out["text"].strip() != ABSTAIN
    assert grounded(out["text"], rag, out["citations"]) is True
    invented = ("Based on the runbooks: restart the flux capacitor and "
                "increase the widget throughput by 42 percent...\n\n"
                "Sources: [volume_anomalies.md]")
    assert grounded(invented, rag, ["volume_anomalies.md"]) is False
