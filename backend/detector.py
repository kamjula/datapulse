"""ML anomaly detection over pipeline telemetry.

Two checks:
  1. Rolling-window robust z-score per metric (median/MAD — fast,
     explainable, immune to baseline contamination).
  2. Discrete schema-drift check (schema_v is categorical, not Gaussian).

Removed Oct 2026: an IsolationForest layer was evaluated and dropped —
ablation (backend/baselines.py, Experiment 1 & 3) showed it added zero
measurable detection value on every tested scenario, scaled or unscaled.
Simpler is better; the eval numbers prove it.

Warm-up: the detector needs ~30 ticks before z-scores are valid.
The demo UI shows a "warming up" state until then.
"""
import os
import numpy as np
from collections import deque

FEATURES = ["rows", "latency_sec", "null_rate", "freshness_min", "dup_rate"]


def _env_float(name: str, default: float) -> float:
    """Read a float config value from the environment.

    Returns ``default`` when the variable is unset. Raises ``ValueError``
    on a non-numeric value so a misconfigured threshold fails fast instead
    of silently running with the wrong sensitivity.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, got {raw!r}")


class AnomalyDetector:
    # Default honored when the matching DATAPULSE_* env var is unset.
    DEFAULT_Z_THRESH = 3.5

    def __init__(self, window: int = 120, z_thresh: float | None = None):
        self.window = window
        self.z_thresh = (
            _env_float("DATAPULSE_Z_THRESH", self.DEFAULT_Z_THRESH)
            if z_thresh is None
            else z_thresh
        )
        self.buf: deque = deque(maxlen=window)
        self._last_schema: int | None = None

    @staticmethod
    def _vec(tick) -> np.ndarray:
        return np.array(
            [tick.rows, tick.latency_sec, tick.null_rate, tick.freshness_min,
             tick.dup_rate],
            dtype=float,
        )

    @property
    def warmed_up(self) -> bool:
        return len(self.buf) >= 30

    def update(self, tick) -> list[dict]:
        events: list[dict] = []
        v = self._vec(tick)

        if len(self.buf) >= 30:
            arr = np.array([self._vec(x) for x in self.buf])
            # Robust z-score (median/MAD): stays accurate even when the
            # baseline window already contains anomalies.
            med = np.median(arr, axis=0)
            mad = np.median(np.abs(arr - med), axis=0) + 1e-9
            z = 0.6745 * (v - med) / mad
            for name, zi in zip(FEATURES, z):
                if abs(zi) >= self.z_thresh:
                    events.append(
                        {
                            "metric": name,
                            "z": round(float(zi), 2),
                            "method": "zscore",
                            "severity": "high" if abs(zi) > 5 else "medium",
                        }
                    )

        if self._last_schema is not None and tick.schema_v != self._last_schema:
            events.append(
                {
                    "metric": "schema_v",
                    "z": None,
                    "method": "schema_drift",
                    "severity": "high",
                    "detail": f"v{self._last_schema} -> v{tick.schema_v}",
                }
            )
        self._last_schema = tick.schema_v

        self.buf.append(tick)
        return events
