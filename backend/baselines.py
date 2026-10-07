"""Baseline comparisons for the DataPulse paper.

Run:  .venv/bin/python -m backend.baselines   (from the project root)

Addresses the obvious reviewer question — "is the combination actually
better than each part alone?" — with ablations over the same seeded
scenario the main eval harness uses (seed=7, 80-tick warmup, each
injectable anomaly run for 30 ticks with 40 settle ticks between).

Experiment 1 — detection ablation:
  * zscore-only / combined: the shipped AnomalyDetector (robust z-score
    + schema-drift check). Both are the same now — the IF layer was
    removed Oct 2026 after this ablation showed it added zero value.
  * if-only: historical result (F1 0.02), recorded in baseline_report.md.
  The discrete schema-drift check is shared infrastructure and stays on.

Experiment 2 — narration baseline:
  * rag-grounded: shipped Narrator + RunbookRAG (citations, abstention)
  * plain-llm    : a no-retrieval stub that mimics a naive LLM prompt —
    free-text diagnosis with generic causes, no citations, never abstains.
  Compared on verifiable properties (citation rate, abstention), not
  prose quality — prose quality needs human rating, so we don't claim it.

All numbers are reproducible: same seeds, same scenario as evals.py.
"""
import os
import sys
from collections import deque

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.simulator import PipelineSimulator, INJECTABLE, MULTIVARIATE
from backend.detector import AnomalyDetector, FEATURES
from backend.rag import RunbookRAG
from backend.narrator import Narrator, ABSTAIN

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_detector(variant: str) -> AnomalyDetector:
    # NOTE (Oct 2026): the IsolationForest layer was removed from
    # detector.py after this ablation showed it added zero value.
    # "zscore-only" and "combined" are now the same shipped detector.
    # "if-only" reruns the removed layer via LegacyIFDetector so the
    # ablation stays reproducible; its numbers are the historical record.
    if variant in ("zscore-only", "combined"):
        return AnomalyDetector()
    if variant == "if-only":
        return LegacyIFDetector()
    raise ValueError(f"unknown variant {variant!r}")


class LegacyIFDetector:
    """The removed IsolationForest layer, kept for ablation reproducibility.

    Faithful copy of the pre-Oct-2026 detector with the z-score layer
    disabled: unscaled IF (contamination=0.03, threshold -0.15), the
    `not events` gate, and the schema-drift check. Not shipped — the
    ablation proved it adds no detection value (see baseline_report.md).
    """

    def __init__(self):
        self.model = IsolationForest(
            n_estimators=100, contamination=0.03, random_state=42
        )
        self.buf: deque = deque(maxlen=120)
        self._fitted = False
        self._last_schema: int | None = None

    @staticmethod
    def _vec(tick) -> np.ndarray:
        return np.array(
            [tick.rows, tick.latency_sec, tick.null_rate, tick.freshness_min,
             tick.dup_rate],
            dtype=float,
        )

    def update(self, tick) -> list:
        events: list = []
        v = self._vec(tick)

        if self._last_schema is not None and tick.schema_v != self._last_schema:
            events.append({"metric": "schema_v", "method": "schema_drift"})
        self._last_schema = tick.schema_v

        if len(self.buf) >= 60:
            arr = np.array([self._vec(x) for x in self.buf])
            if not self._fitted:
                self.model.fit(arr)
                self._fitted = True
            score = float(self.model.decision_function(v.reshape(1, -1))[0])
            if score < -0.15 and not events:
                events.append({"metric": "multivariate",
                               "method": "isolation_forest"})
        self.buf.append(tick)
        return events


def run_detection_variant(variant: str) -> dict:
    """Same scenario as evals.run_detection, detector swapped out."""
    sim = PipelineSimulator(seed=7)
    det = make_detector(variant)
    for _ in range(80):  # warmup on clean data
        det.update(sim.step())

    per_kind = {k: {"tp_ticks": 0, "total_ticks": 0, "delay": None}
                for k in INJECTABLE}
    tp = fp = fn = 0
    for kind in INJECTABLE:
        sim.inject(kind)
        seen_at = None
        for i in range(30):
            tick = sim.step()
            flagged = bool(det.update(tick))
            if tick.injected:
                per_kind[kind]["total_ticks"] += 1
                if flagged:
                    per_kind[kind]["tp_ticks"] += 1
                    tp += 1
                    if seen_at is None:
                        seen_at = i
                        per_kind[kind]["delay"] = i
                else:
                    fn += 1
            elif flagged:
                fp += 1
        for _ in range(40):  # settle between injections
            tick = sim.step()
            if det.update(tick):
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"per_kind": per_kind, "precision": precision, "recall": recall,
            "f1": f1, "fp": fp, "fn": fn}


# --------------------------------------------------------------------------
# Plain-LLM narration baseline (no retrieval): what a naive "just ask the
# LLM" setup produces — plausible-sounding diagnosis, zero grounding.
# --------------------------------------------------------------------------
GENERIC_CAUSES = {
    "rows": "a sudden traffic surge or an upstream retry storm",
    "latency_sec": "resource contention or a slow downstream dependency",
    "null_rate": "an upstream schema or extraction change",
    "freshness_min": "a stalled producer or a broken schedule",
    "schema_v": "an upstream deployment that changed the schema",
    "dup_rate": "an at-least-once producer retrying without idempotency",
    "multivariate": "an interaction between several degrading metrics",
}


class PlainNarrator:
    """No retrieval, no citations, never abstains. Fabricates freely."""

    mode = "plain-llm"

    def narrate(self, incident: dict) -> dict:
        events = incident.get("events", [])
        guesses = "; ".join(
            f"{e['metric']}: likely {GENERIC_CAUSES.get(e['metric'], 'an unknown cause')}"
            for e in events
        ) or "no obvious signal"
        text = (
            f"Incident detected. Probable causes — {guesses}. "
            "Recommend checking the pipeline logs and restarting the "
            "affected job if the issue persists."
        )
        return {"text": text, "mode": self.mode, "citations": []}

    def answer(self, question: str) -> dict:
        return {
            "text": (
                "Based on general data-pipeline knowledge: check your "
                "scheduler logs, look for recent deployments, and verify "
                "upstream data freshness. If that doesn't help, escalate "
                "to the on-call engineer."
            ),
            "mode": self.mode,
            "citations": [],
        }


QUERIES = {
    "volume_spike": "rows volume spike data pipeline anomaly",
    "latency_spike": "latency_sec pipeline latency anomaly",
    "null_surge": "null_rate data quality anomaly",
    "schema_change": "schema_v schema drift anomaly",
    "stale_feed": "freshness_min stale feed anomaly",
    "duplicate_surge": "dup_rate duplicate rows data quality anomaly",
}


def run_narration_baseline() -> dict:
    rag = RunbookRAG(os.path.join(BASE, "runbooks"))
    rag_n = Narrator()
    plain_n = PlainNarrator()

    rows = []
    for kind, q in QUERIES.items():
        cits = rag.search(q)
        incident = {
            "id": 1,
            "events": [{"metric": q.split()[0], "method": "zscore",
                        "z": 6.1, "severity": "high"}],
            "snapshot": {"t": 100},
        }
        r_out = rag_n.narrate(incident, cits)
        p_out = plain_n.narrate(incident)
        rows.append({
            "kind": kind,
            "rag_cites": bool(r_out["citations"]),
            "rag_abstained": r_out["text"].strip() == ABSTAIN,
            "plain_cites": bool(p_out["citations"]),
            "plain_abstained": False,  # by construction: never abstains
        })

    # off-topic question: the hallucination test
    off_topic = "how do I bake a chocolate cake"
    cits = rag.search(off_topic)
    r_off = rag_n.answer(off_topic, cits)
    p_off = plain_n.answer(off_topic)

    return {
        "rows": rows,
        "rag_citation_rate": sum(r["rag_cites"] for r in rows) / len(rows),
        "plain_citation_rate": sum(r["plain_cites"] for r in rows) / len(rows),
        "rag_offtopic_abstains": r_off["text"].strip() == ABSTAIN,
        "plain_offtopic_abstains": False,  # fabricates a generic answer
        "rag_offtopic_text": r_off["text"][:80],
        "plain_offtopic_text": p_off["text"][:80],
    }


# --------------------------------------------------------------------------
# Experiment 3 — multivariate anomalies: can anything catch what the
# univariate z-score misses by design? Adds a scaled-IF variant to test
# whether the IsolationForest layer has value when configured properly.
# (imports moved to top of file)
# --------------------------------------------------------------------------


class ScaledIFDetector:
    """Ablation-only detector: IsolationForest on standardized features.

    Same idea as the shipped IF layer, but features are standardized from
    the warmup window first — otherwise the raw-magnitude feature (rows)
    dominates every split and small-magnitude shifts are invisible.
    """

    def __init__(self, if_thresh: float = -0.15):
        self.if_thresh = if_thresh
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=100, contamination=0.03, random_state=42
        )
        self.buf: deque = deque(maxlen=120)
        self._fitted = False

    @staticmethod
    def _vec(tick) -> np.ndarray:
        return np.array(
            [tick.rows, tick.latency_sec, tick.null_rate, tick.freshness_min,
             tick.dup_rate],
            dtype=float,
        )

    def update(self, tick) -> list:
        events: list = []
        if len(self.buf) >= 60:
            arr = np.array([self._vec(x) for x in self.buf])
            if not self._fitted:
                self.scaler.fit(arr)
                self.model.fit(self.scaler.transform(arr))
                self._fitted = True
            s = self.scaler.transform(self._vec(tick).reshape(1, -1))
            score = float(self.model.decision_function(s)[0])
            if score < self.if_thresh:
                events.append({"metric": "multivariate", "method": "if_scaled"})
        self.buf.append(tick)
        return events


def run_multivariate_variant(variant: str) -> dict:
    """Tick-recall per multivariate anomaly kind, by detector variant."""
    sim = PipelineSimulator(seed=7)
    if variant == "if-scaled":
        det = ScaledIFDetector()
    else:
        det = make_detector(variant)
    for _ in range(80):
        det.update(sim.step())

    per_kind = {}
    for kind in MULTIVARIATE:
        tp = total = 0
        sim.inject(kind)
        for _ in range(30):
            tick = sim.step()
            flagged = bool(det.update(tick))
            if tick.injected:
                total += 1
                if flagged:
                    tp += 1
        for _ in range(40):  # settle between injections
            det.update(sim.step())
        per_kind[kind] = {"tp": tp, "total": total,
                          "recall": tp / total if total else 0.0}
    return per_kind


def main():
    # Experiment 1: if-only reruns the removed IF layer via
    # LegacyIFDetector (reproducible historical record).
    variants = ["zscore-only", "if-only", "combined"]
    det_results = {v: run_detection_variant(v) for v in variants}

    print("# DataPulse baseline report\n")
    print("## Experiment 1 — detection ablation (seeded scenario, seed=7)\n")
    print("if-only = removed IF layer rerun via LegacyIFDetector",
          "(reproducible historical record).\n")
    print("| variant | precision | recall | F1 | false positives | false negatives |")
    print("|---|---|---|---|---|---|")
    for v in variants:
        d = det_results[v]
        print(f"| {v} | {d['precision']:.2f} | {d['recall']:.2f} | "
              f"{d['f1']:.2f} | {d['fp']} | {d['fn']} |")
    print("\nPer-anomaly tick-recall / detection delay (ticks):\n")
    header = "| anomaly | " + " | ".join(variants) + " |"
    print(header)
    print("|" + "---|" * (len(variants) + 1))
    for kind in INJECTABLE:
        cells = []
        for v in variants:
            r = det_results[v]["per_kind"][kind]
            rec = r["tp_ticks"] / r["total_ticks"] if r["total_ticks"] else 0
            delay = r["delay"] if r["delay"] is not None else "missed"
            cells.append(f"{rec:.2f} / {delay}")
        print(f"| {kind} | " + " | ".join(cells) + " |")

    print("\n## Experiment 2 — narration baseline (6 incidents + off-topic)\n")
    n = run_narration_baseline()
    print(f"| setup | citation rate | off-topic abstains |")
    print(f"|---|---|---|")
    print(f"| rag-grounded | {n['rag_citation_rate']:.0%} "
          f"({int(n['rag_citation_rate'] * 6)}/6) | {n['rag_offtopic_abstains']} |")
    print(f"| plain-llm (no retrieval) | {n['plain_citation_rate']:.0%} "
          f"(0/6) | {n['plain_offtopic_abstains']} (fabricates) |")
    print()
    print(f"RAG off-topic reply: \"{n['rag_offtopic_text']}...\"")
    print(f"Plain off-topic reply: \"{n['plain_offtopic_text']}...\"")

    print("\n## Experiment 3 — multivariate anomalies "
          "(correlated, sub-threshold shifts)\n")
    mv_variants = ["zscore-only", "if-only", "combined", "if-scaled"]
    mv = {v: run_multivariate_variant(v) for v in mv_variants}
    print("| anomaly | " + " | ".join(mv_variants) + " |")
    print("|" + "---|" * (len(mv_variants) + 1))
    for kind in MULTIVARIATE:
        cells = [f"{mv[v][kind]['recall']:.2f}" for v in mv_variants]
        print(f"| {kind} | " + " | ".join(cells) + " |")
    print("\nrecall = fraction of injected ticks flagged. "
          "z-score misses by design (each shift < 3.5 sigma).")


if __name__ == "__main__":
    main()
