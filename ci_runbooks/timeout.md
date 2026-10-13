# CI Failure: Job Timeout

## Symptoms
- `The job running on runner has exceeded the maximum execution time`.
- `##[error]The operation was canceled` after a long running step.
- A step that normally takes minutes runs until the platform kills it.

## Likely cause
- A test or process is hanging: waiting on network, a lock, or user input.
- An accidental infinite loop or a retry loop that never gives up.
- The job genuinely outgrew the default time limit after adding heavy steps.

## Fix
- Find the last log line before the hang: that step is the suspect.
- Add a per-step timeout so the failing step surfaces instead of the whole job.
- Cache dependencies before raising the overall job limit.
