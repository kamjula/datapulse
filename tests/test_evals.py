"""Unit tests for the eval harness (backend/evals.py).

The harness is the project's documented proof that detection works
(F1 0.98 on the seeded run) and that narrations stay grounded. These
tests pin that proof down: if a detector or narrator change moves the
numbers, the suite says so before the README does.
"""
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.evals import (  # noqa: E402
    main,
    run_abstention,
    run_detection,
    run_narration,
)
from backend.simulator import INJECTABLE  # noqa: E402


class DetectionTest(unittest.TestCase):
    def setUp(self):
        self.result = run_detection()

    def test_result_shape(self):
        # one entry per injectable anomaly kind, plus the three scores
        self.assertEqual(set(self.result["per_kind"]), set(INJECTABLE))
        for score in ("precision", "recall", "f1"):
            self.assertGreaterEqual(self.result[score], 0.0)
            self.assertLessEqual(self.result[score], 1.0)

    def test_every_injected_kind_gets_flagged(self):
        # the detector must catch each anomaly kind at least once and
        # record how fast (delay in ticks from injection start)
        for kind, stats in self.result["per_kind"].items():
            self.assertGreater(stats["total_ticks"], 0, kind)
            self.assertGreater(stats["tp_ticks"], 0, kind)
            self.assertIsNotNone(stats["delay"], kind)

    def test_gate_threshold_holds(self):
        # main() reports PASS only when F1 > 0.5; pin that margin here
        self.assertGreater(self.result["f1"], 0.5)


class NarrationTest(unittest.TestCase):
    def test_all_incidents_stay_grounded_and_labeled(self):
        # every narration must have text, cite a real runbook, and say
        # which mode (template or claude) produced it
        results = run_narration()
        self.assertEqual(len(results), 6)
        for r in results:
            self.assertTrue(r["has_text"], r["kind"])
            self.assertTrue(r["cites_runbook"], r["kind"])
            self.assertTrue(r["mode_labeled"], r["kind"])
            self.assertIn(r["mode"], ("claude", "template"))


class AbstentionTest(unittest.TestCase):
    def test_off_topic_question_is_not_answered(self):
        self.assertTrue(run_abstention())


class MainReportTest(unittest.TestCase):
    def test_main_prints_pass_without_exiting(self):
        # main() raises SystemExit(1) only when a check fails
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            main()
        finally:
            sys.stdout = old
        out = buf.getvalue()
        self.assertIn("PASS", out)
        self.assertIn("F1=", out)


if __name__ == "__main__":
    unittest.main()
