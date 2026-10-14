"""Unit tests for the runbook retriever (backend/rag.py).

Covers the retrieve -> cite behavior of the TF-IDF runbook index: the
right runbook wins for a symptom query, every hit carries source/text/
score, and off-topic queries return nothing instead of noise. Also the
TOC parsing and the empty-library guard. All deterministic -- no
network, no model calls.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from rag import RunbookRAG  # noqa: E402

RUNBOOKS = os.path.join(os.path.dirname(__file__), "..", "runbooks")


class RetrieverTest(unittest.TestCase):
    def setUp(self):
        self.rag = RunbookRAG(RUNBOOKS)

    def test_library_loads_all_runbooks_with_toc(self):
        self.assertTrue(self.rag.docs)
        self.assertEqual(len(self.rag.toc), 6)
        self.assertIn("null_surge.md", self.rag.toc)

    def test_toc_parses_title_and_sections(self):
        toc = self.rag.toc["duplicate_surge.md"]
        self.assertEqual(toc["title"], "Runbook: Duplicate Row Surge")
        self.assertEqual(
            toc["sections"], ["Symptoms", "Likely causes", "Checks", "Fix"]
        )

    def test_search_hits_carry_source_text_and_score(self):
        hits = self.rag.search("duplicate rows idempotency keys", k=3)
        self.assertTrue(hits)
        self.assertLessEqual(len(hits), 3)
        scores = []
        for hit in hits:
            self.assertIn("source", hit)
            self.assertIn("text", hit)
            self.assertIn("score", hit)
            self.assertIn(hit["source"], self.rag.toc)  # cite a real file
            self.assertGreater(hit["score"], 0)
            self.assertLessEqual(hit["score"], 1.0)
            scores.append(hit["score"])
        self.assertEqual(scores, sorted(scores, reverse=True))  # best first

    def test_search_finds_the_right_runbook(self):
        cases = {
            "duplicate rows surging idempotency keys": "duplicate_surge.md",
            "null_rate jumping to 10 percent": "null_surge.md",
            "latency spike batches slow warehouse contention": "latency_spike.md",
            "schema changed column renamed type changed": "schema_drift.md",
            "feed is stale rows not landing freshness": "stale_feed.md",
        }
        for query, expected in cases.items():
            hits = self.rag.search(query, k=1)
            self.assertTrue(hits, f"no hit for query: {query!r}")
            self.assertEqual(hits[0]["source"], expected, f"query: {query!r}")

    def test_search_abstains_on_irrelevant_query(self):
        # Out-of-domain question: TF-IDF scores are all zero, so the
        # retriever returns nothing instead of a garbage citation.
        hits = self.rag.search("quantum banana piano sonata", k=3)
        self.assertEqual(hits, [])

    def test_search_respects_k(self):
        hits = self.rag.search("duplicate rows", k=1)
        self.assertLessEqual(len(hits), 1)

    def test_empty_library_raises(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(RuntimeError):
                RunbookRAG(empty)

    def test_section_headings_returns_first_n(self):
        headings = self.rag.section_headings("duplicate_surge.md", n=3)
        self.assertEqual(headings, ["Symptoms", "Likely causes", "Checks"])

    def test_section_headings_unknown_source_returns_empty(self):
        self.assertEqual(self.rag.section_headings("nope.md"), [])


if __name__ == "__main__":
    unittest.main()
