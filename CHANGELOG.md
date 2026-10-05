# Changelog

All notable changes to DataPulse are documented here.

## [1.0.0] — 2026-10-04

First stable release. DataPulse is a GenAI Data Reliability Copilot:
ML detects pipeline anomalies, a RAG runbook copilot explains them with
citations, and a live chaos panel lets anyone break the pipeline and
watch the AI diagnose it.

**Verified numbers (synthetic, seeded & reproducible):**
detection precision 0.96 · recall 1.00 · F1 0.98 across 7 anomaly types,
0-tick detection delay, narration grounding + abstention tests green.

### The 15-day release plan (days 1–14)

- **Day 1** — Repo hygiene: MIT license, README badges, eval harness
  exit codes.
- **Day 2** — New chaos scenario `duplicate_surge` (burst of duplicate
  rows) + `dup_rate` metric and its runbook.
- **Day 3** — Detector thresholds via env vars: `DATAPULSE_Z_THRESH`
  (default 3.5) and `DATAPULSE_IF_THRESH` (default -0.15), documented in
  README "Configuration".
- **Day 4** — "Export .md" button on the incident panel: downloads the
  incident (events, diagnosis, citations) as Markdown.
- **Day 5** — Structured checklist in the incident API payload: top 3
  runbook section headings from the cited runbooks, rendered under the
  diagnosis.
- **Day 6** — Weekly seasonality in the simulator baseline volume
  (day-of-week factor, seed reproducibility kept; eval F1 stayed > 0.9).
- **Day 7** — Copilot Q&A shows retrieval scores: "matched:
  null_surge.md (0.87)" style labels per source.
- **Day 8** — Chaos keyboard shortcuts: number keys 1–6 trigger the
  chaos injections, documented in the panel tooltip.
- **Day 9** — Eval latency benchmark: detection throughput (ticks/sec)
  and p95 per-tick detector latency in ms, printed as a table.
- **Day 10** — Severity escalation hint: 3+ high-severity incidents
  within 10 minutes adds an amber "consider paging on-call" banner.
- **Day 11** — Slimmer Docker build context: hardened `.dockerignore`
  (`.git/`, `Dockerfile`, depth-proof `__pycache__`/`*.pyc` excludes).
- **Day 12** — Incident timeline with severity colors, relative
  timestamps ("2 min ago"), click to expand the diagnosis.
- **Day 13** — `/incidents` pagination + filter: `?severity=`,
  `?limit=`, `?offset=`; the frontend timeline uses them.
- **Day 14** — Architecture diagram (mermaid: simulator → detector →
  RAG → narrator → dashboard) in README, plus a 60-second recruiter
  demo script (what to click, what to say).
- **Day 15** — This release: CHANGELOG.md + the `v1.0.0` tag.

### Known limitations

- The Day 9 latency benchmark currently reports p95 detector latency of
  ~7–8 ms against the 5 ms gate on the runner. This is a documented,
  honest finding — not a release blocker — and is tracked as future work
  (detector optimization: window-array caching, fewer IsolationForest
  trees). It is not "fixed" by weakening the threshold.

[1.0.0]: https://github.com/kamjula/datapulse/releases/tag/v1.0.0
