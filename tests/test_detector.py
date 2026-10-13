"""Unit tests for the anomaly detector (backend/detector.py).

Covers the two shipped checks: rolling-window robust z-score per metric
and the schema-drift check. All ticks are hand-built so the tests are
fast and deterministic -- no simulator randomness involved.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from detector import AnomalyDetector  # noqa: E402
from simulator import Tick  # noqa: E402


def clean_tick(t, schema_v=1):
    # Steady baseline with a little natural wiggle so MAD is nonzero.
    return Tick(
        t=t,
        rows=1000 + (t % 7),
        latency_sec=2.0 + (t % 5) * 0.01,
        null_rate=0.01,
        freshness_min=30.0,
        schema_v=schema_v,
        dup_rate=0.005,
    )


def spike_tick(t, **overrides):
    tick = clean_tick(t)
    for key, value in overrides.items():
        setattr(tick, key, value)
    return tick


class DetectorTest(unittest.TestCase):
    def feed(self, det, ticks):
        events = []
        for tick in ticks:
            events.extend(det.update(tick))
        return events

    def test_clean_baseline_has_no_false_positives(self):
        det = AnomalyDetector()
        events = self.feed(det, [clean_tick(t) for t in range(60)])
        self.assertEqual(events, [])

    def test_big_rows_spike_is_detected_as_high(self):
        det = AnomalyDetector()
        self.feed(det, [clean_tick(t) for t in range(30)])
        events = det.update(spike_tick(30, rows=8000))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metric"], "rows")
        self.assertEqual(events[0]["method"], "zscore")
        self.assertEqual(events[0]["severity"], "high")

    def test_moderate_spike_is_medium_severity(self):
        det = AnomalyDetector()
        self.feed(det, [clean_tick(t) for t in range(30)])
        events = det.update(spike_tick(30, rows=1014))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["severity"], "medium")

    def test_spike_before_warmup_is_ignored(self):
        det = AnomalyDetector()
        self.feed(det, [clean_tick(t) for t in range(5)])
        events = det.update(spike_tick(5, rows=8000))
        self.assertEqual(events, [])

    def test_schema_change_is_flagged(self):
        det = AnomalyDetector()
        self.feed(det, [clean_tick(t, schema_v=1) for t in range(5)])
        events = det.update(clean_tick(5, schema_v=2))
        drift = [e for e in events if e["method"] == "schema_drift"]
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["metric"], "schema_v")
        self.assertEqual(drift[0]["severity"], "high")
        self.assertEqual(drift[0]["detail"], "v1 -> v2")

    def test_same_schema_version_has_no_drift_event(self):
        det = AnomalyDetector()
        events = self.feed(det, [clean_tick(t, schema_v=3) for t in range(40)])
        self.assertEqual(events, [])

    def test_env_var_threshold_overrides_default(self):
        os.environ["DATAPULSE_Z_THRESH"] = "10000"
        self.addCleanup(os.environ.pop, "DATAPULSE_Z_THRESH", None)
        det = AnomalyDetector()
        self.feed(det, [clean_tick(t) for t in range(30)])
        # Same spike that fires at the default 3.5 stays quiet here.
        self.assertEqual(det.update(spike_tick(30, rows=8000)), [])

    def test_non_numeric_env_var_fails_fast(self):
        os.environ["DATAPULSE_Z_THRESH"] = "abc"
        self.addCleanup(os.environ.pop, "DATAPULSE_Z_THRESH", None)
        with self.assertRaises(ValueError):
            AnomalyDetector()

    def test_buffer_stays_capped_at_window(self):
        det = AnomalyDetector(window=50)
        self.feed(det, [clean_tick(t) for t in range(80)])
        self.assertEqual(len(det.buf), 50)


if __name__ == "__main__":
    unittest.main()
