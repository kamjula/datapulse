---
title: DataPulse — GenAI Data Reliability Copilot
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# ⚡ DataPulse — GenAI Data Reliability Copilot

![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4+-orange)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
![CI](https://github.com/kamjula/datapulse/actions/workflows/ci.yml/badge.svg)

**ML detects, GenAI explains.** A live data-pipeline watchdog where an ML
anomaly detector flags telemetry issues and a GenAI copilot writes the
root-cause diagnosis — grounded in a runbook library, with citations and an
eval harness to prove it works.

## Why this exists

Data downtime is expensive, but most "AI observability" demos are black
boxes. DataPulse shows the full loop that hiring managers actually ask
about in Data Scientist / Applied AI interviews:

```
telemetry ──► ML detection ──► RAG over runbooks ──► GenAI diagnosis
(z-score +        (citations,          (abstains instead of
 IsolationForest)  abstention)         hallucinating)
```

## Features

- **Live pipeline simulator** — emits rows, latency, null-rate, freshness,
  schema version every second (seeded, reproducible).
- **ML anomaly detection** — robust z-score (median/MAD, immune to baseline
  contamination) + IsolationForest for multivariate drift + discrete
  schema-drift check.
- **Chaos panel** — inject 6 failure modes live: volume spike/drop, latency
  spike, null surge, schema change, stale feed. Detection delay: **0 ticks**.
- **GenAI root-cause narration** — incident context + retrieved runbook
  excerpts → concise diagnosis with `[source]` citations. Claude API when
  `ANTHROPIC_API_KEY` is set, deterministic template fallback otherwise
  (the UI always labels which mode produced the text).
- **Abstention guardrail** — off-topic questions get "not in the runbooks"
  instead of a hallucinated answer.
- **Copilot Q&A** — ask about pipeline failures in plain English, answered
  from the runbooks.
- **Eval harness** (`backend/evals.py`) — detection precision/recall/F1 per
  anomaly, detection delay, narration-grounding checks, abstention test.

## Eval results (seeded, reproducible)

| anomaly | tick-recall | detection delay |
|---|---|---|
| volume_spike | 1.00 | 0 ticks |
| volume_drop | 1.00 | 0 ticks |
| latency_spike | 1.00 | 0 ticks |
| null_surge | 1.00 | 0 ticks |
| schema_change | 1.00 | 0 ticks |
| stale_feed | 1.00 | 0 ticks |

Overall: **precision 0.92 · recall 1.00 · F1 0.96** · all narrations cite a
runbook and label their generation mode · abstention holds.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run evals (no API key needed)
python -m backend.evals

# start the live demo
uvicorn backend.app:app --port 8000
# open http://localhost:8000
```

Optional: `export ANTHROPIC_API_KEY=...` for Claude-powered narrations.

## Demo script (60 seconds for a recruiter)

1. Open the dashboard, point at the live telemetry charts.
2. Hit **null surge** in the chaos panel.
3. Watch the incident card appear: ML flags `null_rate` (z≈40), the copilot
   writes the diagnosis citing `[null_surge.md]`.
4. Ask the copilot: *"what do I do about a null surge?"*
5. Mention: evals are in the repo — F1 0.96, abstention guardrail, zero
   hallucinated runbook answers.

## Roadmap

- [ ] Postgres-backed incident history + weekly reliability report
- [ ] LLM-as-judge scoring for narration quality in evals
- [ ] Slack/PagerDuty webhook on high-severity incidents
- [ ] Real connector: plug in dbt / Airflow metadata instead of the simulator

## Stack

Python · FastAPI · scikit-learn · TF-IDF RAG · Claude API · vanilla JS dashboard
