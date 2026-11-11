"""Tests that the timeline drops expanded ids that fell off the capped history.

The backend keeps only the newest MAX_INCIDENTS incidents and never reuses
ids, so an expanded id older than that window can never come back. Without
pruning, window._expanded only grows over a long session.
"""
import os
import re
import subprocess
import unittest

FRONTEND = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "index.html"
)


def _frontend_html():
    with open(FRONTEND, encoding="utf-8") as fh:
        return fh.read()


def _prune_fn_source():
    html = _frontend_html()
    m = re.search(r"(function pruneExpanded\(newestId, maxKept\) \{.*?\n\})", html, re.S)
    assert m, "pruneExpanded not found in frontend"
    return m.group(1)


def _run_prune(expanded, newest, cap):
    fn = _prune_fn_source()
    cap_js = "undefined" if cap is None else str(cap)
    script = (
        f"var window = {{ _expanded: new Set([{', '.join(map(str, expanded))}]) }};\n"
        + fn
        + f"\npruneExpanded({newest}, {cap_js});\n"
        "console.log([...window._expanded].sort((a, b) => a - b).join(','));\n"
    )
    out = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


class TestFrontendExpandedPrune(unittest.TestCase):
    def test_fetch_prunes_with_backend_cap(self):
        html = _frontend_html()
        # Newest id tracked across pages/filters, then pruned with the
        # cap the backend reports (not a hardcoded copy of it).
        self.assertIn("window._newestId", html)
        self.assertIn("pruneExpanded(window._newestId, inc.max_incidents)", html)

    def test_prune_drops_only_ids_older_than_the_window(self):
        # Real function from the page, run in node: newest id 250,
        # backend keeps 200, so ids 1..50 are gone and 51..250 stay.
        self.assertEqual(_run_prune([1, 50, 51, 250], 250, 200), "51,250")

    def test_prune_keeps_everything_under_the_cap(self):
        self.assertEqual(_run_prune([1, 2, 3], 3, 200), "1,2,3")

    def test_prune_is_a_noop_without_newest_or_cap(self):
        # Old backend with no max_incidents, or no incidents yet: leave
        # the set alone instead of wiping it.
        for newest, cap in [(0, 200), (250, 0), (250, None)]:
            self.assertEqual(_run_prune([1, 2], newest, cap), "1,2")


if __name__ == "__main__":
    unittest.main()
