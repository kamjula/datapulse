"""Unit tests for the API helpers in backend/app.py.

The HTTP routes need a running server, so these cover the pure helpers
the routes are built on: event summaries, incident severity, the
escalation-hint rule, and the runbook checklist. fastapi and pydantic
are stubbed here so the module imports with the standard library only.
"""
import os
import sys
import types
import unittest

# Stubs: the helpers under test never touch the web stack, so fake the
# two imports instead of pulling in fastapi/pydantic.
_fastapi = types.ModuleType("fastapi")
_responses = types.ModuleType("fastapi.responses")
_responses.FileResponse = lambda *args, **kwargs: None  # noqa: E731


class _FastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def _route(self, *args, **kwargs):
        def wrap(fn):
            return fn

        return wrap

    get = _route
    post = _route
    on_event = _route


_fastapi.FastAPI = _FastAPI
_fastapi.responses = _responses

_pydantic = types.ModuleType("pydantic")


class _BaseModel:
    pass


_pydantic.BaseModel = _BaseModel

sys.modules["fastapi"] = _fastapi
sys.modules["fastapi.responses"] = _responses
sys.modules["pydantic"] = _pydantic

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import app as api  # noqa: E402


def incident(i, start_t, severities):
    return {
        "id": i,
        "start_t": start_t,
        "events": [{"metric": "rows", "severity": s} for s in severities],
    }


class TestSummarizeEvents(unittest.TestCase):
    def test_joins_metric_names(self):
        events = [{"metric": "rows"}, {"metric": "latency_sec"}]
        self.assertEqual(
            api._summarize_events(events), "rows latency_sec data pipeline anomaly"
        )

    def test_single_event(self):
        self.assertEqual(
            api._summarize_events([{"metric": "null_rate"}]),
            "null_rate data pipeline anomaly",
        )


class TestIncidentSeverity(unittest.TestCase):
    def test_high_when_any_signal_high(self):
        inc = incident(1, 10, ["normal", "high"])
        self.assertEqual(api._incident_severity(inc), "high")

    def test_normal_when_no_high(self):
        inc = incident(1, 10, ["normal", "normal"])
        self.assertEqual(api._incident_severity(inc), "normal")

    def test_normal_for_empty_events(self):
        self.assertEqual(api._incident_severity({"id": 1, "events": []}), "normal")


class TestEscalationIds(unittest.TestCase):
    def test_three_high_in_window_get_hint(self):
        now = 1000
        incs = [
            incident(1, now - 100, ["high"]),
            incident(2, now - 300, ["high"]),
            incident(3, now - 500, ["high"]),
            incident(4, now - 100, ["normal"]),
        ]
        self.assertEqual(api._escalation_ids(incs, now), {1, 2, 3})

    def test_two_high_is_not_enough(self):
        now = 1000
        incs = [incident(1, now - 100, ["high"]), incident(2, now - 200, ["high"])]
        self.assertEqual(api._escalation_ids(incs, now), set())

    def test_old_incidents_do_not_count(self):
        now = 1000
        incs = [
            incident(1, now - api.ESCALATION_WINDOW - 1, ["high"]),
            incident(2, now - 100, ["high"]),
            incident(3, now - 200, ["high"]),
        ]
        self.assertEqual(api._escalation_ids(incs, now), set())

    def test_exactly_at_window_edge_counts(self):
        now = 1000
        incs = [
            incident(1, now - api.ESCALATION_WINDOW, ["high"]),
            incident(2, now - 100, ["high"]),
            incident(3, now - 200, ["high"]),
        ]
        self.assertEqual(api._escalation_ids(incs, now), {1, 2, 3})

    def test_normal_severity_never_counts(self):
        now = 1000
        incs = [incident(i, now - 10 * i, ["normal"]) for i in (1, 2, 3)]
        self.assertEqual(api._escalation_ids(incs, now), set())


class TestBuildChecklist(unittest.TestCase):
    def test_checklist_uses_top_three_headings(self):
        out = api._build_checklist([{"source": "latency_spike.md"}])
        self.assertEqual(
            out,
            [
                {"source": "latency_spike.md", "heading": "Symptoms"},
                {"source": "latency_spike.md", "heading": "Likely causes"},
                {"source": "latency_spike.md", "heading": "Checks"},
            ],
        )

    def test_same_source_listed_once(self):
        cits = [{"source": "null_surge.md"}, {"source": "null_surge.md"}]
        out = api._build_checklist(cits)
        sources = {c["source"] for c in out}
        self.assertEqual(sources, {"null_surge.md"})
        self.assertEqual(len(out), 3)

    def test_n_sections_caps_headings(self):
        out = api._build_checklist([{"source": "stale_feed.md"}], n_sections=1)
        self.assertEqual(out, [{"source": "stale_feed.md", "heading": "Symptoms"}])

    def test_unknown_source_contributes_nothing(self):
        out = api._build_checklist([{"source": "nope.md"}])
        self.assertEqual(out, [])


class TestLastN(unittest.TestCase):
    def test_zero_returns_nothing(self):
        self.assertEqual(api._last_n([1, 2, 3], 0), [])

    def test_negative_returns_nothing(self):
        self.assertEqual(api._last_n([1, 2, 3], -5), [])

    def test_returns_last_n_in_order(self):
        self.assertEqual(api._last_n([1, 2, 3, 4, 5], 2), [4, 5])

    def test_n_larger_than_history_returns_all(self):
        self.assertEqual(api._last_n([1, 2, 3], 120), [1, 2, 3])

    def test_huge_n_is_capped_not_an_error(self):
        hist = list(range(10))
        self.assertEqual(api._last_n(hist, 100000), hist)


class TestSeriesRoute(unittest.TestCase):
    def _step(self, n):
        for _ in range(n):
            api.sim.step()

    def test_n_zero_returns_no_points(self):
        self._step(5)
        self.assertEqual(api.series(n=0)["points"], [])

    def test_negative_n_returns_no_points(self):
        self._step(5)
        self.assertEqual(api.series(n=-3)["points"], [])

    def test_n_returns_last_points_in_order(self):
        self._step(5)
        out = api.series(n=2)
        hist = list(api.sim.history)
        self.assertEqual(
            [p["t"] for p in out["points"]], [tk.t for tk in hist[-2:]]
        )

    def test_unknown_metric_falls_back_to_rows(self):
        self._step(5)
        out = api.series(metric="bogus", n=2)
        self.assertEqual(out["metric"], "rows")
        self.assertEqual(len(out["points"]), 2)


if __name__ == "__main__":
    unittest.main()
