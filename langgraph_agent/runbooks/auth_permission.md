# CI Failure: Auth or Permission

## Symptoms
- `403 Forbidden`, `401 Unauthorized`, or `Permission denied` in a push/deploy step.
- `Resource not accessible by integration` from the GitHub API.
- Deploy steps fail while build and test steps pass.

## Likely cause
- The workflow token lacks the permission scope the step needs.
- A secret expired, was rotated, or was never set in this repository.
- The step runs from a fork, where secrets are intentionally unavailable.

## Fix
- Check the workflow `permissions:` block for the scope named in the error.
- Verify the secret exists under this repository's settings (names are case-sensitive).
- For forks, expect secret-using steps to be skipped or to fail by design.
