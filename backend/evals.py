"""Eval harness for DataPulse.

Run:  .venv/bin/python -m backend.evals   (from the project root)

Measures:
  1. Detection quality — per-anomaly recall, overall precision/recall/F1,
     and detection delay (ticks from injection start to first flag).
  2. Narration grounding — every incident narration must cite a runbook and
     label its generation mode (no silent LLM output).
  3. Abstention — an off-topic question must NOT get a made-up answer.
  4. Latency — detector throughput (ticks/sec) and p95 per-tick detector
     latency in ms (target: p95 < 5ms).

The simulator is seeded, so these numbers are reproducible.
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.simulator import PipelineSimulator, INJECTABLE
from backend.detector import AnomalyDetector
from backend.rag import RunbookRAG
from backend.narrator import Narrator, ABSTAIN

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Section 4 budget: p95 per-tick detector latency must stay under this.
P95_LATENCY_BUDGET_MS = 5.0


def run_detection() -> dict:
    sim = PipelineSimulator(seed=7)
    det = AnomalyDetector()
    # warmup on clean data
    for _ in range(80):
        det.update(sim.step())

    per_kind = {k: {"tp_ticks": 0, "total_ticks": 0, "delay": None} for k in INJECTABLE}
    tp = fp = fn = 0
    for kind in INJECTABLE:
        sim.inject(kind)
        seen_at = None
        for i in range(30):  # longer than any injection duration
            tick = sim.step()
            events = det.update(tick)
            flagged = bool(events)
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
        # settle back to normal between injections
        for _ in range(40):
            tick = sim.step()
            if det.update(tick):
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"per_kind": per_kind, "precision": precision, "recall": recall, "f1": f1}


def run_narration() -> list[dict]:
    rag = RunbookRAG(os.path.join(BASE, "runbooks"))
    narrator = Narrator()
    results = []
    queries = {
        "volume_spike": "rows volume spike data pipeline anomaly",
        "latency_spike": "latency_sec pipeline latency anomaly",
        "null_surge": "null_rate data quality anomaly",
        "schema_change": "schema_v schema drift anomaly",
        "stale_feed": "freshness_min stale feed anomaly",
        "duplicate_surge": "dup_rate duplicate rows data quality anomaly",
    }
    for kind, q in queries.items():
        cits = rag.search(q)
        out = narrator.narrate(
            {"id": 1, "events": [{"metric": q.split()[0], "method": "zscore",
                                  "z": 6.1, "severity": "high"}], "snapshot": {"t": 100}},
            cits,
        )
        results.append(
            {
                "kind": kind,
                "has_text": bool(out["text"]),
                "cites_runbook": any(c.endswith(".md") for c in out["citations"]),
                "mode_labeled": out["mode"] in ("claude", "template"),
                "mode": out["mode"],
            }
        )
    return results


def run_abstention() -> bool:
    rag = RunbookRAG(os.path.join(BASE, "runbooks"))
    narrator = Narrator()
    cits = rag.search("how do I bake a chocolate cake")
    out = narrator.answer("how do I bake a chocolate cake", cits)
    return out["text"].strip() == ABSTAIN


def run_latency(n_ticks: int = 2000, warmup: int = 200) -> dict:
    """Section 4: detector latency benchmark.

    Warms the detector up fully first (rolling window filled, IsolationForest
    fitted) so the numbers reflect steady-state production-like cost rather
    than cold-start fitting, then times ``AnomalyDetector.update`` per tick.
    """
    sim = PipelineSimulator(seed=99)
    det = AnomalyDetector()
    for _ in range(warmup):
        det.update(sim.step())

    lat_ns = []
    for _ in range(n_ticks):
        tick = sim.step()
        t0 = time.perf_counter_ns()
        det.update(tick)
        lat_ns.append(time.perf_counter_ns() - t0)

    lat_ns.sort()
    total_s = sum(lat_ns) / 1e9

    def pct(p: float) -> float:
        # nearest-rank percentile, in milliseconds
        k = max(0, min(len(lat_ns) - 1, math.ceil(p / 100 * len(lat_ns)) - 1))
        return lat_ns[k] / 1e6

    return {
        "ticks": n_ticks,
        "throughput": n_ticks / total_s if total_s else 0.0,
        "p50_ms": pct(50),
        "p95_ms": pct(95),
        "max_ms": lat_ns[-1] / 1e6,
    }


def main():
    print("# DataPulse eval report\n")
    d = run_detection()
    print("## 1. Detection quality\n")
    print("| anomaly | tick-recall | detection delay (ticks) |")
    print("|---|---|---|")
    for kind, r in d["per_kind"].items():
        rec = r["tp_ticks"] / r["total_ticks"] if r["total_ticks"] else 0
        delay = r["delay"] if r["delay"] is not None else "missed"
        print(f"| {kind} | {rec:.2f} | {delay} |")
    print(f"\nOverall: precision={d['precision']:.2f} "
          f"recall={d['recall']:.2f} F1={d['f1']:.2f}\n")

    print("## 2. Narration grounding\n")
    print("| incident | text | cites runbook | mode labeled | mode |")
    print("|---|---|---|---|---|")
    for r in run_narration():
        print(f"| {r['kind']} | {r['has_text']} | {r['cites_runbook']} "
              f"| {r['mode_labeled']} | {r['mode']} |")
    print()

    ok = run_abstention()
    print("## 3. Abstention guardrail\n")
    print(f"Off-topic question abstained (no hallucination): {ok}\n")

    lat = run_latency()
    lat_ok = lat["p95_ms"] < P95_LATENCY_BUDGET_MS
    print("## 4. Latency benchmark\n")
    print("| metric | value |")
    print("|---|---|")
    print(f"| ticks measured | {lat['ticks']} |")
    print(f"| throughput | {lat['throughput']:.0f} ticks/sec |")
    print(f"| p50 per-tick latency | {lat['p50_ms']:.3f} ms |")
    print(f"| p95 per-tick latency | {lat['p95_ms']:.3f} ms |")
    print(f"| max per-tick latency | {lat['max_ms']:.3f} ms |")
    print(f"\nTarget: p95 < {P95_LATENCY_BUDGET_MS:.0f} ms "
          f"-> {'OK' if lat_ok else 'OVER BUDGET'}\n")

    checks = (
        d["f1"] > 0.5
        and all(r["cites_runbook"] and r["mode_labeled"] for r in run_narration())
        and ok
        and lat_ok
    )
    print("PASS" if checks else "FAIL",
          "- thresholds: F1>0.5, all narrations cited+labeled, "
          "abstention holds, p95<5ms")
    if not checks:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
