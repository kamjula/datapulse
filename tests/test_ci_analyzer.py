"""Unit tests for the CI failure analyzer (stdlib unittest, no network)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ci_analyzer import CIFailureAnalyzer, extract_error_lines


class TestExtractErrorLines(unittest.TestCase):
    def test_picks_signal_lines_only(self):
        log = "installing deps\nERROR: package missing\nall good here\nTests FAILED"
        lines = extract_error_lines(log)
        self.assertEqual(len(lines), 2)
        self.assertIn("ERROR: package missing", lines)

    def test_dedupes_and_caps(self):
        log = "\n".join(["error happened"] * 100)
        lines = extract_error_lines(log)
        self.assertEqual(lines, ["error happened"])

    def test_empty_log(self):
        self.assertEqual(extract_error_lines(""), [])


class TestAnalyze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analyzer = CIFailureAnalyzer()

    def test_dependency_log(self):
        log = "ERROR: No matching distribution found for pandas==9.9.9"
        r = self.analyzer.analyze(log)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["category"], "dependency_resolution")
        self.assertTrue(r["citations"])

    def test_abstains_on_clean_log(self):
        r = self.analyzer.analyze("Build finished. All checks passed.")
        self.assertEqual(r["status"], "abstain")

    def test_abstains_on_empty_log(self):
        r = self.analyzer.analyze("")
        self.assertEqual(r["status"], "abstain")

    def test_cause_and_fix_present(self):
        log = (
            "Run black --check .\n"
            "would reformat src/app.py\n"
            "1 file would be reformatted, 4 files would be left unchanged.\n"
            "Error: Process completed with exit code 1."
        )
        r = self.analyzer.analyze(log)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["category"], "lint_format")
        self.assertTrue(r["likely_cause"])
        self.assertTrue(r["suggested_fix"])


if __name__ == "__main__":
    unittest.main()
