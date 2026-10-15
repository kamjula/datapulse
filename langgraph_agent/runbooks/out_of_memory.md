# CI Failure: Out of Memory

## Symptoms
- `Killed` as the only explanation for a dead process.
- `MemoryError`, `Cannot allocate memory`, or exit code 137.
- JavaScript heap errors: `JavaScript heap out of memory` during a build.

## Likely cause
- A step loads a whole dataset or file into memory instead of streaming it.
- Parallel test workers multiplied memory use past the runner limit.
- A build step (bundler, compiler) needs a larger heap than the default.

## Fix
- Check which step died and what it was processing when it died.
- Reduce worker parallelism or stream the input in chunks.
- Raise the heap flag for that one step (for example NODE_OPTIONS) rather than everywhere.
