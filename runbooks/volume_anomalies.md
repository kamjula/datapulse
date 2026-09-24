# Runbook: Volume Spike / Volume Drop

## Symptoms
- `rows` metric jumps to 2x+ of baseline (spike) or collapses below 50% of
  baseline (drop) for several consecutive ticks.
- Downstream dashboards may show inflated totals or missing data.

## Likely causes
- Spike: upstream backfill or replay job running, duplicate partition writes,
  a new source onboarded without notice.
- Drop: upstream extractor failed silently, partition filter too aggressive,
  source system outage.

## Checks
1. Compare `rows` against the same hour last 7 days in the warehouse.
2. Check the orchestrator for manual / backfill DAG runs in the last hour.
3. Look for duplicate `partition_key` values in the landing table.

## Fix
- Spike from backfill: let it finish, then de-duplicate with
  `ROW_NUMBER() OVER (PARTITION BY id ORDER BY loaded_at DESC)`.
- Drop from extractor failure: re-run the extractor for the missing window and
  backfill before the next SLA checkpoint.
- Page the data engineering on-call if the anomaly persists > 15 minutes.
