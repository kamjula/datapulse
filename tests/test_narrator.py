"""Tests for backend/narrator.py template mode.

The narrator has two modes: "claude" (needs ANTHROPIC_API_KEY) and
"template" (deterministic fallback). These tests only cover template mode
and the abstain guardrail, so they run with zero API cost and no keys.
"""
import os
import unittest

from backend.narrator import ABSTAIN, Narrator


def _incident():
    return {
        "id": 3,
        "snapshot": {"t": 42},
        "events": [
            {
                "metric": "rows",
                "method": "z-score",
                "z": 5.2,
                "severity": "high",
                "detail": "z=5.2",
            },
        ],
    }


def _citations():
    return [
        {
            "source": "volume_anomalies.md",
            "text": "## Symptoms\nRow volume suddenly spikes when an upstream backfill lands.",
            "score": 0.9,
        }
    ]


class TestNarratorTemplate(unittest.TestCase):
    def setUp(self):
        # template mode is the default with no API key around
        self.saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        self.n = Narrator()

    def tearDown(self):
        if self.saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = self.saved

    def test_defaults_to_template_mode(self):
        self.assertEqual(self.n.mode, "template")

    def test_narrate_abstains_without_citations(self):
        out = self.n.narrate(_incident(), [])
        self.assertEqual(out["text"], ABSTAIN)
        self.assertEqual(out["mode"], "template")
        self.assertEqual(out["citations"], [])

    def test_narrate_returns_shape(self):
        out = self.n.narrate(_incident(), _citations())
        self.assertEqual(out["mode"], "template")
        self.assertEqual(out["citations"], ["volume_anomalies.md"])
        self.assertIn("**Incident #3**", out["text"])
        self.assertIn("tick 42", out["text"])
        self.assertIn("row volume", out["text"])  # metric label, not raw key
        self.assertIn("z-score", out["text"])
        self.assertIn("high", out["text"])
        self.assertIn("volume anomaly (spike or drop)", out["text"])
        self.assertIn("[volume_anomalies.md]", out["text"])

    def test_narrate_unknown_metric_uses_raw_name(self):
        incident = {"id": 1, "snapshot": {"t": 7}, "events": [
            {"metric": "weird_metric", "method": "z-score", "severity": "low"}]}
        out = self.n.narrate(incident, _citations())
        self.assertIn("weird_metric", out["text"])

    def test_narrate_unknown_runbook_area(self):
        cites = [{"source": "some_new_thing.md", "text": "stuff", "score": 0.5}]
        out = self.n.narrate(_incident(), cites)
        self.assertIn("pipeline anomaly", out["text"])

    def test_narrate_without_detail_falls_back_to_z(self):
        incident = {"id": 2, "snapshot": {}, "events": [
            {"metric": "latency_sec", "method": "z-score", "z": 4.1, "severity": "medium"}]}
        out = self.n.narrate(incident, _citations())
        self.assertIn("z=4.1", out["text"])
        self.assertIn("pipeline latency", out["text"])

    def test_answer_abstains_without_citations(self):
        out = self.n.answer("why are rows spiking?", [])
        self.assertEqual(out["text"], ABSTAIN)
        self.assertEqual(out["citations"], [])

    def test_answer_uses_snippet_and_dedupes_sources(self):
        cites = [
            {"source": "volume_anomalies.md", "text": "spike detail one", "score": 0.9},
            {"source": "volume_anomalies.md", "text": "spike detail two", "score": 0.8},
        ]
        out = self.n.answer("why are rows spiking?", cites)
        self.assertTrue(out["text"].startswith("Based on the runbooks:"))
        self.assertIn("spike detail one", out["text"])
        self.assertEqual(out["text"].count("[volume_anomalies.md]"), 1)

    def test_answer_skips_bare_title_chunk(self):
        cites = [
            {"source": "volume_anomalies.md", "text": "# Runbook: volume", "score": 0.9},
            {"source": "volume_anomalies.md", "text": "## Checks\nlook at the backfill log", "score": 0.8},
        ]
        out = self.n.answer("what do I check?", cites)
        self.assertIn("backfill log", out["text"])
        self.assertNotIn("Runbook: volume", out["text"].split("Sources:")[0])

    def test_claude_failure_falls_back_to_template(self):
        # fail-safe: a broken API call must never break the demo
        def _boom(*args, **kwargs):
            raise RuntimeError("network down")

        self.n._client_or_raise = _boom
        self.n.mode = "claude"
        out = self.n.narrate(_incident(), _citations())
        self.assertEqual(out["mode"], "template")
        self.assertIn("template fallback used", out["text"])
        self.assertIn("row volume", out["text"])

    def test_answer_claude_failure_falls_back_to_template(self):
        def _boom(*args, **kwargs):
            raise RuntimeError("network down")

        self.n._client_or_raise = _boom
        self.n.mode = "claude"
        out = self.n.answer("why?", _citations())
        self.assertEqual(out["mode"], "template")
        self.assertIn("Based on the runbooks:", out["text"])


if __name__ == "__main__":
    unittest.main()
