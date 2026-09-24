# Runbook: Schema Drift

## Symptoms
- `schema_v` increments unexpectedly; downstream queries may break or
  silently change meaning.
- Column renames, type changes, or dropped columns in the landing table.

## Likely causes
- Source team deployed a schema change without notifying consumers.
- Ingestion auto-evolution picked up a new field with an incompatible type.

## Checks
1. Diff the current schema against the last known-good snapshot.
2. Check the source team's release notes and the ingestion connector config.
3. Run downstream dbt / SQL tests to see what breaks.

## Fix
- Pin the consumer to the previous schema version and add an explicit cast /
  rename mapping for the changed field.
- Require schema-change approval in the ingestion connector going forward.
- Announce the change in the data-contracts channel with migration notes.
