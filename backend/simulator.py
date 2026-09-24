"""Simulates a data pipeline emitting telemetry ticks.

Each tick carries: rows processed, latency, null rate, freshness and schema
version. Anomalies can be injected on demand (used by the live demo and the
eval harness). All randomness is seeded so evals are reproducible.
"""
import math
import random
from collections import deque
from dataclasses import dataclass, asdict


@dataclass
class Tick:
    t: int
    rows: float
    latency_sec: float
    null_rate: float
    freshness_min: float
    schema_v: int
    injected: str | None = None

    def to_dict(self):
        return asdict(self)


INJECTABLE = [
    "volume_spike",
    "volume_drop",
    "latency_spike",
    "null_surge",
    "schema_change",
    "stale_feed",
]

_DURATIONS = {
    "volume_spike": 12,
    "volume_drop": 15,
    "latency_spike": 10,
    "null_surge": 12,
    "schema_change": 1,
    "stale_feed": 20,
}


class PipelineSimulator:
    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        self.t = 0
        self.schema_v = 3
        self.active: tuple[str, int] | None = None
        self.history: deque[Tick] = deque(maxlen=2000)

    def inject(self, kind: str) -> bool:
        if kind not in INJECTABLE:
            return False
        self.active = (kind, _DURATIONS[kind])
        return True

    def step(self) -> Tick:
        self.t += 1
        r = self.rng
        rows = 5000 + 300 * math.sin(self.t / 25) + r.gauss(0, 250)
        latency = 4.0 + 0.4 * math.sin(self.t / 40) + r.gauss(0, 0.35)
        null_rate = 0.012 + r.gauss(0, 0.004)
        freshness = 6 + r.gauss(0, 1.5)
        injected = None

        if self.active:
            kind, rem = self.active
            injected = kind
            if kind == "volume_spike":
                rows *= 3.2
            elif kind == "volume_drop":
                rows *= 0.25
            elif kind == "latency_spike":
                latency *= 4.5
            elif kind == "null_surge":
                null_rate = 0.18 + r.gauss(0, 0.02)
            elif kind == "schema_change":
                self.schema_v += 1
            elif kind == "stale_feed":
                freshness = 45 + r.gauss(0, 5)
            rem -= 1
            self.active = (kind, rem) if rem > 0 else None

        tick = Tick(
            t=self.t,
            rows=max(rows, 0),
            latency_sec=max(latency, 0.1),
            null_rate=min(max(null_rate, 0.0), 1.0),
            freshness_min=max(freshness, 0.0),
            schema_v=self.schema_v,
            injected=injected,
        )
        self.history.append(tick)
        return tick
