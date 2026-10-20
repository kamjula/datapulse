"""Tests for the small deterministic helpers in backend/llm_evals.py.

Complements tests/test_llm_evals.py, which covers the dataset labels and
the main grounded() path. These cover the helpers that path relies on:
_flat, _runbook_text, and the grounded() edge cases.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.llm_evals import KB, _flat, _runbook_text, grounded
from backend.rag import RunbookRAG


class FlatTest(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(_flat("  a\n b\t\tc  "), "a b c")
        self.assertEqual(_flat(""), "")
        self.assertEqual(_flat("already flat"), "already flat")


class RunbookTextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = RunbookRAG(KB)

    def test_joins_all_chunks_of_a_source(self):
        text = _runbook_text(self.rag, "null_surge.md")
        self.assertIn("null_rate", text)        # real content from the runbook
        self.assertNotIn("\n", text)            # flattened to one line
        self.assertEqual(text, text.strip())
        self.assertGreater(len(self.rag.docs), 1)  # joined every chunk, not just the first

    def test_unknown_source_is_empty(self):
        self.assertEqual(_runbook_text(self.rag, "does_not_exist.md"), "")


class GroundedEdgesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rag = RunbookRAG(KB)

    def test_empty_answer_body_is_not_grounded(self):
        answer = "Based on the runbooks:\n\nSources: [null_surge.md]"
        self.assertFalse(grounded(answer, self.rag, ["null_surge.md"]))

    def test_answer_without_sources_marker_checks_whole_body(self):
        # no "Sources:" marker -> the whole body is treated as the snippet
        self.assertFalse(grounded("restart the flux capacitor", self.rag,
                                  ["null_surge.md"]))

    def test_trailing_ellipsis_stripped_before_matching(self):
        snippet = _runbook_text(self.rag, "null_surge.md")[:120]
        answer = f"Based on the runbooks: {snippet}...\n\nSources: [null_surge.md]"
        self.assertTrue(grounded(answer, self.rag, ["null_surge.md"]))

    def test_snippet_cited_against_wrong_runbook_fails(self):
        snippet = _runbook_text(self.rag, "null_surge.md")[:80]
        answer = f"Based on the runbooks: {snippet}\n\nSources: [latency_spike.md]"
        self.assertFalse(grounded(answer, self.rag, ["latency_spike.md"]))


if __name__ == "__main__":
    unittest.main()
