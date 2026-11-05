"""Unit tests for the pipeline simulator (backend/simulator.py).

Covers the weekly seasonality curve (repeats weekly, dips on the
weekend, no sharp jumps), seeded reproducibility of the tick stream,
and the injected anomalies: each kind flags its ticks, runs for exactly
its listed duration, and pushes the right metric in the right direction.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from simulator import (  # noqa: E402
    INJECTABLE,
    MULTIVARIATE,
    TICKS_PER_DAY,
    WEEKLY_AMPLITUDE,
    PipelineSimulator,
    Tick,
    _DURATIONS,
    weekly_factor,
)


class WeeklyFactorTest(unittest.TestCase):
    def test_repeats_every_week(self):
        week = 7 * TICKS_PER_DAY
        for t in (0, 17, 200, 333):
            self.assertAlmostEqual(weekly_factor(t), weekly_factor(t + week), places=12)

    def test_stays_within_expected_band(self):
        for t in range(7 * TICKS_PER_DAY):
            factor = weekly_factor(t)
            self.assertGreaterEqual(factor, 1.0 - WEEKLY_AMPLITUDE)
            self.assertLessEqual(factor, 1.0)

    def test_dips_on_saturday_midday(self):
        # day-of-week 5.5 = Saturday midday is the bottom of the curve.
        bottom = int(5.5 * TICKS_PER_DAY)
        self.assertEqual(weekly_factor(bottom), 1.0 - WEEKLY_AMPLITUDE)
        self.assertLess(weekly_factor(bottom), weekly_factor(0))  # Monday 00:00

    def test_no_step_jumps(self):
        # smooth cosine: neighbouring ticks barely differ.
        jumps = [
            abs(weekly_factor(t + 1) - weekly_factor(t))
            for t in range(7 * TICKS_PER_DAY)
        ]
        self.assertLess(max(jumps), 0.01)


class ReproducibilityTest(unittest.TestCase):
    def run_ticks(self, seed, n):
        sim = PipelineSimulator(seed=seed)
        return [sim.step().to_dict() for _ in range(n)]

    def test_same_seed_same_stream(self):
        self.assertEqual(self.run_ticks(7, 200), self.run_ticks(7, 200))

    def test_different_seed_different_stream(self):
        self.assertNotEqual(self.run_ticks(7, 50), self.run_ticks(9, 50))

    def test_tick_counter_increments(self):
        sim = PipelineSimulator(seed=7)
        ticks = [sim.step() for _ in range(10)]
        self.assertEqual([tick.t for tick in ticks], list(range(1, 11)))


class InjectionTest(unittest.TestCase):
    def warm_up(self, sim, n=200):
        return [sim.step() for _ in range(n)]

    def inject_and_collect(self, sim, kind):
        self.assertTrue(sim.inject(kind))
        return [sim.step() for _ in range(_DURATIONS[kind])]

    def test_unknown_kind_rejected(self):
        sim = PipelineSimulator(seed=7)
        self.assertFalse(sim.inject("not_a_real_anomaly"))
        self.assertIsNone(sim.step().injected)

    def test_second_inject_while_active_is_rejected(self):
        sim = PipelineSimulator(seed=7)
        self.warm_up(sim)
        self.assertTrue(sim.inject("volume_spike"))
        stepped = [sim.step() for _ in range(3)]
        self.assertTrue(all(t.injected == "volume_spike" for t in stepped))
        # Second inject must not cut the first one short.
        self.assertFalse(sim.inject("latency_spike"))
        rest = [sim.step() for _ in range(10)]
        self.assertTrue(all(t.injected == "volume_spike" for t in rest[:9]))
        self.assertIsNone(rest[9].injected)
        # Once finished, injecting again works as before.
        self.assertTrue(sim.inject("latency_spike"))

    def test_same_kind_reinject_while_active_keeps_remaining(self):
        sim = PipelineSimulator(seed=7)
        self.warm_up(sim)
        self.assertTrue(sim.inject("volume_spike"))
        sim.step()
        self.assertFalse(sim.inject("volume_spike"))
        self.assertEqual(sim.active, ("volume_spike", 11))

    def test_every_kind_flags_ticks_for_exact_duration(self):
        for kind in INJECTABLE + MULTIVARIATE:
            sim = PipelineSimulator(seed=7)
            self.warm_up(sim)
            flagged = self.inject_and_collect(sim, kind)
            self.assertTrue(all(tick.injected == kind for tick in flagged), kind)
            self.assertIsNone(sim.step().injected)  # injection is over

    def test_schema_change_bumps_version_once(self):
        sim = PipelineSimulator(seed=7)
        self.warm_up(sim)
        before = sim.schema_v
        sim.inject("schema_change")
        sim.step()
        self.assertEqual(sim.schema_v, before + 1)
        self.assertIsNone(sim.step().injected)

    def test_volume_spike_inflates_rows(self):
        sim = PipelineSimulator(seed=7)
        baseline = self.warm_up(sim)
        base_mean = sum(t.rows for t in baseline[-48:]) / 48
        spiked = self.inject_and_collect(sim, "volume_spike")
        spike_mean = sum(t.rows for t in spiked) / len(spiked)
        self.assertGreater(spike_mean, 2.5 * base_mean)

    def test_volume_drop_deflates_rows(self):
        sim = PipelineSimulator(seed=7)
        baseline = self.warm_up(sim)
        base_mean = sum(t.rows for t in baseline[-48:]) / 48
        dropped = self.inject_and_collect(sim, "volume_drop")
        drop_mean = sum(t.rows for t in dropped) / len(dropped)
        self.assertLess(drop_mean, 0.5 * base_mean)

    def test_latency_spike(self):
        sim = PipelineSimulator(seed=7)
        baseline = self.warm_up(sim)
        base_mean = sum(t.latency_sec for t in baseline[-48:]) / 48
        spiked = self.inject_and_collect(sim, "latency_spike")
        spike_mean = sum(t.latency_sec for t in spiked) / len(spiked)
        self.assertGreater(spike_mean, 3.0 * base_mean)

    def test_null_surge(self):
        sim = PipelineSimulator(seed=7)
        self.warm_up(sim)
        surged = self.inject_and_collect(sim, "null_surge")
        surge_mean = sum(t.null_rate for t in surged) / len(surged)
        self.assertGreater(surge_mean, 0.1)  # baseline is ~0.012

    def test_stale_feed(self):
        sim = PipelineSimulator(seed=7)
        self.warm_up(sim)
        stale = self.inject_and_collect(sim, "stale_feed")
        stale_mean = sum(t.freshness_min for t in stale) / len(stale)
        self.assertGreater(stale_mean, 30.0)  # baseline is ~6 min

    def test_duplicate_surge(self):
        sim = PipelineSimulator(seed=7)
        self.warm_up(sim)
        surged = self.inject_and_collect(sim, "duplicate_surge")
        dup_mean = sum(t.dup_rate for t in surged) / len(surged)
        self.assertGreater(dup_mean, 0.2)  # baseline is ~0.001


class TickBoundsTest(unittest.TestCase):
    def test_fields_stay_in_valid_ranges(self):
        sim = PipelineSimulator(seed=7)
        for _ in range(500):
            tick = sim.step()
            self.assertGreaterEqual(tick.rows, 0)
            self.assertGreaterEqual(tick.latency_sec, 0.1)
            self.assertGreaterEqual(tick.null_rate, 0.0)
            self.assertLessEqual(tick.null_rate, 1.0)
            self.assertGreaterEqual(tick.freshness_min, 0.0)
            self.assertGreaterEqual(tick.dup_rate, 0.0)
            self.assertLessEqual(tick.dup_rate, 1.0)

    def test_history_keeps_recent_ticks(self):
        sim = PipelineSimulator(seed=7)
        for _ in range(100):
            sim.step()
        self.assertEqual(len(sim.history), 100)
        self.assertEqual(sim.history[-1].t, 100)

    def test_to_dict_round_trips_fields(self):
        tick = Tick(t=1, rows=100.0, latency_sec=2.0, null_rate=0.01,
                    freshness_min=5.0, schema_v=3)
        as_dict = tick.to_dict()
        self.assertEqual(as_dict["t"], 1)
        self.assertEqual(as_dict["schema_v"], 3)
        self.assertEqual(as_dict["dup_rate"], 0.0)
        self.assertIsNone(as_dict["injected"])


if __name__ == "__main__":
    unittest.main()
