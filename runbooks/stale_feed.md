# Runbook: Stale Feed (Freshness Breach)

## Symptoms
- `freshness_min` climbs well above the 15-minute SLA; dashboards show
  yesterday's data.
- No new partitions landing in the raw bucket.

## Likely causes
- Upstream cron / scheduler missed its run or is stuck.
- Credentials for the source system expired.
- Network partition between the source and the landing zone.

## Checks
1. Check the scheduler for failed or stuck runs in the last 2 hours.
2. Verify source credentials and API health status.
3. Check object-store write permissions for the landing bucket.

## Fix
- Re-run the missed extraction and backfill to restore freshness.
- Rotate expired credentials and add an expiry alert 7 days ahead.
- Add a freshness SLA monitor that pages before the dashboard goes stale.
