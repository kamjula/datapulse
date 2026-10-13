# CI Failure: Test Assertion Failure

## Symptoms
- `FAILED` lines in the test summary with an `AssertionError`.
- `assert x == y` showing two values that should match but do not.
- The same test passes locally but fails in CI, or fails after a code change in the same PR.

## Likely cause
- A real regression: the code change altered behaviour the test was checking.
- The test depends on data, ordering, or environment that changed.
- An expected value in the test is stale after an intentional behaviour change.

## Fix
- Read the assertion values first: decide whether the code or the expectation is wrong.
- Reproduce locally with the exact failing test name before changing anything.
- If the behaviour change was intentional, update the test and say why in the PR.
