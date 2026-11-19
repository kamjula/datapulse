"""Tests that the dashboard charts every telemetry series the backend serves.

The 60-second demo walkthrough promises charts for rows, latency,
null-rate, freshness, duplicate rate and schema version. The schema
version chart went missing: the backend serves schema_v, but the
frontend never asked for it, so injecting a schema change was
invisible in the telemetry section. Keep the chart list in sync with
what the backend can serve.
"""
import os
import re
import unittest

from backend.detector import FEATURES

FRONTEND = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "index.html"
)


def _charted_metrics():
    with open(FRONTEND, encoding="utf-8") as fh:
        html = fh.read()
    block = re.search(r"const METRICS = \[(.*?)\];", html, re.S).group(1)
    return re.findall(r'"(\w+)"', block)


class TestChartedMetrics(unittest.TestCase):
    def test_charts_cover_every_series(self):
        # FEATURES is what the detector tracks; schema_v is the extra
        # series /api/series serves (categorical, not Gaussian).
        self.assertEqual(_charted_metrics(), FEATURES + ["schema_v"])

    def test_every_charted_metric_is_served(self):
        # A typo here would 400 on every poll, so check each charted
        # metric is one the backend actually serves.
        served = FEATURES + ["schema_v"]
        for metric in _charted_metrics():
            self.assertIn(metric, served, f"{metric} is not served")


if __name__ == "__main__":
    unittest.main()
