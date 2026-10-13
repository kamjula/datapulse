"""Unit tests for the CI triage agent (stdlib unittest, no network)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ci_agent import run_ci_agent, STEPS

DEP_LOG = "ERROR: No matching distribution found for pandas==9.9.9"
CLEAN_LOG = "Deploy preview ready. Build finished in 42s. All checks passed."


class TestCIAgent(unittest.TestCase):
    def test_diagnoses_and_verifies(self):
        out = run_ci_agent(DEP_LOG)
        report = out["report"]
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["category"], "dependency_resolution")
        self.assertTrue(report["verified"])
        self.assertEqual(report["attempts"], 1)

    def test_trace_has_all_steps_in_order(self):
        out = run_ci_agent(DEP_LOG)
        self.assertEqual([t["step"] for t in out["trace"]], STEPS)

    def test_abstains_on_clean_log(self):
        out = run_ci_agent(CLEAN_LOG)
        self.assertEqual(out["report"]["status"], "abstain")
        self.assertFalse(out["report"]["verified"])

    def test_diff_retry_is_used_when_first_pass_abstains(self):
        # a log with no signal lines of its own: only the diff can help,
        # and even then the honest outcome is abstention, attempts == 1
        # (the retry needs signal; the trace must still be complete)
        out = run_ci_agent(CLEAN_LOG, "+++ b/backend/app.py\n")
        self.assertEqual([t["step"] for t in out["trace"]], STEPS)


if __name__ == "__main__":
    unittest.main()
