"""ML anomaly detection over pipeline telemetry.

Two layers:
  1. Rolling-window z-score per metric (fast, explainable).
  2. IsolationForest on the multivariate feature vector (catches
     interactions a single metric would miss).
Plus a discrete schema-drift check (schema_v is categorical, not Gaussian).

Warm-up: the detector needs ~30 ticks before z-scores and ~60 before the
IsolationForest is fitted. The demo UI shows a "warming up" state until then.
"""
import os
import numpy as np
from collections import deque
from sklearn.ensemble import IsolationForest

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
    # Defaults honored when the matching DATAPULSE_* env var is unset.
    DEFAULT_Z_THRESH = 3.5
    DEFAULT_IF_THRESH = -0.15

    def __init__(self, window: int = 120, z_thresh: float | None = None,
                 if_thresh: float | None = None):
        self.window = window
        self.z_thresh = (
            _env_float("DATAPULSE_Z_THRESH", self.DEFAULT_Z_THRESH)
            if z_thresh is None
            else z_thresh
        )
        self.if_thresh = (
            _env_float("DATAPULSE_IF_THRESH", self.DEFAULT_IF_THRESH)
            if if_thresh is None
            else if_thresh
        )
        self.buf: deque = deque(maxlen=window)
        self.model = IsolationForest(
            n_estimators=100, contamination=0.03, random_state=42
        )
        self._fitted = False
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

        if len(self.buf) >= 60:
            arr = np.array([self._vec(x) for x in self.buf])
            if not self._fitted:
                self.model.fit(arr)
                self._fitted = True
            score = float(self.model.decision_function(v.reshape(1, -1))[0])
            if score < self.if_thresh and not events:
                events.append(
                    {
                        "metric": "multivariate",
                        "z": round(score, 3),
                        "method": "isolation_forest",
                        "severity": "low",
                    }
                )

        self.buf.append(tick)
        return events
