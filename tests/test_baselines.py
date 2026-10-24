"""Unit tests for the paper baselines (backend/baselines.py).

Covers the fast, deterministic parts of the ablation setup: the
plain-LLM narration baseline (fabricates causes, cites nothing, never
abstains), the detector-variant factory, and the two IF detectors' basic
behavior. The full scenario runners (run_detection_variant,
run_narration_baseline, run_multivariate_variant) take minutes, so they
stay out of unit tests and run through main().
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.baselines import (  # noqa: E402
    GENERIC_CAUSES,
    QUERIES,
    LegacyIFDetector,
    PlainNarrator,
    ScaledIFDetector,
    make_detector,
)
from backend.detector import AnomalyDetector  # noqa: E402
from backend.narrator import ABSTAIN  # noqa: E402
from backend.simulator import Tick  # noqa: E402


def clean_tick(t, schema_v=1):
    return Tick(
        t=t,
        rows=1000 + (t % 7),
        latency_sec=2.0 + (t % 5) * 0.01,
        null_rate=0.01,
        freshness_min=30.0,
        schema_v=schema_v,
        dup_rate=0.005,
    )


def incident_with(*metrics):
    return {
        "id": 1,
        "events": [
            {"metric": m, "method": "zscore", "z": 6.1, "severity": "high"}
            for m in metrics
        ],
        "snapshot": {"t": 100},
    }


class PlainNarratorTest(unittest.TestCase):
    def test_narrate_returns_text_mode_and_no_citations(self):
        out = PlainNarrator().narrate(incident_with("latency_sec"))
        self.assertEqual(out["mode"], "plain-llm")
        self.assertEqual(out["citations"], [])
        self.assertTrue(out["text"])

    def test_narrate_names_a_cause_for_each_metric(self):
        n = PlainNarrator()
        for metric, cause in GENERIC_CAUSES.items():
            out = n.narrate(incident_with(metric))
            self.assertIn(cause, out["text"], f"missing cause for {metric}")

    def test_narrate_falls_back_on_unknown_metric(self):
        out = PlainNarrator().narrate(incident_with("mystery_metric"))
        self.assertIn("an unknown cause", out["text"])

    def test_narrate_with_no_events_says_so_plainly(self):
        out = PlainNarrator().narrate({"id": 1, "events": [], "snapshot": {}})
        self.assertIn("no obvious signal", out["text"])

    def test_answer_fabricates_generic_advice_with_no_citations(self):
        out = PlainNarrator().answer("why is my pipeline slow")
        self.assertEqual(out["mode"], "plain-llm")
        self.assertEqual(out["citations"], [])
        self.assertIn("scheduler logs", out["text"])

    def test_never_abstains(self):
        n = PlainNarrator()
        self.assertNotEqual(
            n.narrate(incident_with("rows"))["text"].strip(), ABSTAIN
        )
        self.assertNotEqual(
            n.answer("how do I bake a chocolate cake")["text"].strip(), ABSTAIN
        )


class GenericCausesTest(unittest.TestCase):
    def test_covers_every_narratable_metric(self):
        self.assertEqual(
            set(GENERIC_CAUSES),
            {
                "rows", "latency_sec", "null_rate", "freshness_min",
                "schema_v", "dup_rate", "multivariate",
            },
        )

    def test_causes_are_plain_nonempty_strings(self):
        for metric, cause in GENERIC_CAUSES.items():
            self.assertIsInstance(cause, str)
            self.assertTrue(cause.strip(), f"empty cause for {metric}")


class QueriesTest(unittest.TestCase):
    def test_one_query_per_narration_kind(self):
        self.assertEqual(
            set(QUERIES),
            {
                "volume_spike", "latency_spike", "null_surge",
                "schema_change", "stale_feed", "duplicate_surge",
            },
        )

    def test_query_first_token_is_a_known_metric(self):
        # run_narration_baseline uses q.split()[0] as the event metric,
        # so it must always be one of the narratable metrics.
        for kind, query in QUERIES.items():
            self.assertIn(
                query.split()[0], GENERIC_CAUSES,
                f"query {kind!r} starts with an unknown metric",
            )


class MakeDetectorTest(unittest.TestCase):
    def test_zscore_only_and_combined_give_the_shipped_detector(self):
        # NOTE (Oct 2026): the IF layer was removed after the ablation
        # showed it added zero value, so both variants must now return
        # the same shipped detector.
        for variant in ("zscore-only", "combined"):
            det = make_detector(variant)
            self.assertIsInstance(det, AnomalyDetector)
            self.assertNotIsInstance(det, LegacyIFDetector)

    def test_if_only_gives_the_legacy_detector(self):
        self.assertIsInstance(make_detector("if-only"), LegacyIFDetector)

    def test_unknown_variant_raises(self):
        for bad in ("if", "zscore", "", "IF-ONLY"):
            with self.assertRaises(ValueError, msg=f"variant {bad!r}"):
                make_detector(bad)


class LegacyIFDetectorTest(unittest.TestCase):
    def test_vec_has_five_features(self):
        self.assertEqual(len(LegacyIFDetector._vec(clean_tick(0))), 5)

    def test_schema_drift_event_fires_on_version_change(self):
        det = LegacyIFDetector()
        det.update(clean_tick(0, schema_v=1))
        events = det.update(clean_tick(1, schema_v=2))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metric"], "schema_v")
        self.assertEqual(events[0]["method"], "schema_drift")

    def test_no_event_when_schema_version_is_unchanged(self):
        det = LegacyIFDetector()
        det.update(clean_tick(0, schema_v=1))
        self.assertEqual(det.update(clean_tick(1, schema_v=1)), [])

    def test_no_flags_before_warmup(self):
        det = LegacyIFDetector()
        for t in range(59):
            self.assertEqual(det.update(clean_tick(t)), [])

    def test_update_always_returns_a_list(self):
        det = LegacyIFDetector()
        for t in range(3):
            self.assertIsInstance(det.update(clean_tick(t)), list)


class ScaledIFDetectorTest(unittest.TestCase):
    def test_vec_has_five_features(self):
        self.assertEqual(len(ScaledIFDetector._vec(clean_tick(0))), 5)

    def test_no_flags_before_warmup(self):
        det = ScaledIFDetector()
        for t in range(59):
            self.assertEqual(det.update(clean_tick(t)), [])


if __name__ == "__main__":
    unittest.main()
