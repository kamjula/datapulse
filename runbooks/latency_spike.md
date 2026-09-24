# Runbook: Latency Spike

## Symptoms
- `latency_sec` rises to 3x+ of baseline; batches take much longer than usual.
- SLA breach risk if p95 latency stays elevated.

## Likely causes
- Expensive new transformation deployed (e.g. unfiltered join, regex on raw text).
- Warehouse contention: another team's heavy query sharing the same cluster.
- Data skew: one partition suddenly much larger than the rest.

## Checks
1. Check the query plan of the latest deployed transformation for full scans.
2. Look at warehouse query history for concurrent heavy queries.
3. Check partition size distribution for skew.

## Fix
- Roll back the most recent transformation change and re-deploy with a filter
  pushdown or incremental model.
- If contention: move the pipeline to a dedicated warehouse or reschedule the
  conflicting job.
- For skew: repartition on a higher-cardinality key.
