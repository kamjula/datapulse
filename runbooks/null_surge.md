# Runbook: Null Rate Surge

## Symptoms
- `null_rate` jumps from ~1% baseline to 10%+; data quality monitors fire.
- Downstream ML features built on the affected columns degrade.

## Likely causes
- Source schema change: a field was renamed or stopped being populated.
- Upstream API started returning null for a deprecated field.
- Join key mismatch after a dimension table reload.

## Checks
1. Identify which columns went null with a per-column null profile query.
2. Diff the source schema against yesterday's snapshot.
3. Check the upstream API changelog / release notes.

## Fix
- Map the renamed field in the ingestion layer and backfill the gap.
- Add a NOT NULL contract test on critical columns so this fails fast next time.
- Notify downstream ML owners to retrain or pin features if the gap is large.
