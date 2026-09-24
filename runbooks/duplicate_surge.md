# Runbook: Duplicate Row Surge

## Symptoms
- `dup_rate` jumps from ~0.1% baseline to 30%+; row volume inflates ~1.6x while distinct business keys stay flat.
- Downstream aggregates (counts, sums) overstate reality; ML training sets get label leakage from repeated rows.

## Likely causes
- Upstream producer retry storm: a failed batch was retried without idempotency keys, re-emitting the same rows.
- CDC/connector misconfiguration: snapshot + incremental loads overlapping after a connector restart.
- Merge/upsert job lost its deduplication step after a deploy.

## Checks
1. Confirm with a duplicate-key query: `SELECT key, COUNT(*) c FROM events GROUP BY key HAVING c > 1 ORDER BY c DESC LIMIT 20`.
2. Check the producer's retry/dead-letter metrics around the surge window — look for 5xx spikes preceding it.
3. Diff the last deploy of the ingestion/merge job; verify the dedup stage still runs.

## Fix
- Quarantine the duplicated partition and re-run the dedup (e.g. `ROW_NUMBER() OVER (PARTITION BY key ORDER BY ingested_at DESC) = 1`).
- Enforce idempotency keys on the producer and make retries safe.
- Add a `dup_rate` contract test on the silver table so the next surge pages within minutes, not days.
