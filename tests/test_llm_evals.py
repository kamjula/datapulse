"""Tests for the LLM-output eval harness (backend/llm_evals.py)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm_evals import ANSWERABLE, KB, UNANSWERABLE, grounded
from backend.narrator import ABSTAIN, Narrator
from backend.rag import RunbookRAG


class DatasetTest(unittest.TestCase):
    def test_dataset_labels_point_at_real_runbooks(self):
        rag = RunbookRAG(KB)
        sources = {d["source"] for d in rag.docs}
        for _, expected in ANSWERABLE:
            self.assertIn(expected, sources)
        self.assertGreaterEqual(len(ANSWERABLE), 8)
        self.assertGreaterEqual(len(UNANSWERABLE), 3)


class GroundedTest(unittest.TestCase):
    def test_grounded_check_accepts_real_answer_and_rejects_invented_one(self):
        rag = RunbookRAG(KB)
        narrator = Narrator()
        question, _ = ANSWERABLE[0]
        out = narrator.answer(question, rag.search(question))
        self.assertNotEqual(out["text"].strip(), ABSTAIN)
        self.assertTrue(grounded(out["text"], rag, out["citations"]))
        invented = ("Based on the runbooks: restart the flux capacitor and "
                    "increase the widget throughput by 42 percent...\n\n"
                    "Sources: [volume_anomalies.md]")
        self.assertFalse(grounded(invented, rag, ["volume_anomalies.md"]))


if __name__ == "__main__":
    unittest.main()
