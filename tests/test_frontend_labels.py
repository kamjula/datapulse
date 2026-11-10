"""Tests that the frontend shows human metric labels, not raw names.

The narrator fixed this on the backend in PR #50, but the timeline and the
Markdown export in frontend/index.html still printed raw names like
"dup_rate". These tests keep the frontend label map in sync with
backend/narrator.py METRIC_LABELS and make sure both display spots use it.
"""
import os
import re
import unittest

from backend.narrator import METRIC_LABELS as BACKEND_LABELS

FRONTEND = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "index.html"
)


def _frontend_labels():
    with open(FRONTEND, encoding="utf-8") as fh:
        html = fh.read()
    block = re.search(r"const METRIC_LABELS = \{(.*?)\};", html, re.S).group(1)
    return dict(re.findall(r'(\w+): "([^"]+)"', block)), html


class TestFrontendLabels(unittest.TestCase):
    def test_labels_match_backend(self):
        labels, _ = _frontend_labels()
        for key, value in BACKEND_LABELS.items():
            self.assertEqual(labels.get(key), value, f"frontend label for {key}")
        self.assertEqual(set(labels), set(BACKEND_LABELS))

    def test_both_display_spots_use_labels(self):
        _, html = _frontend_labels()
        self.assertIn("metricLabel(e.metric)", html)
        # No raw metric name left in a display string (the ?metric= API
        # query param is not a display spot, so it is not matched here).
        self.assertNotIn("${e.metric}", html)
        self.assertNotIn("- ${e.metric}", html)

    def test_unknown_metric_falls_back_to_raw_name(self):
        _, html = _frontend_labels()
        self.assertIn("return METRIC_LABELS[m] || m;", html)


if __name__ == "__main__":
    unittest.main()
