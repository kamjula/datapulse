# CI Failure: Lint or Format Check

## Symptoms
- `would reformat` from black, or flake8/ruff findings listed as errors.
- The failing step is a lint, format, or type-check step, not a test step.
- Errors point at style, unused imports, or formatting only.

## Likely cause
- Code was committed without running the formatter locally.
- The local formatter version differs from the CI version, so they disagree.
- A new lint rule was enabled in config without fixing existing code.

## Fix
- Run the same formatter and linter versions as CI before pushing.
- Auto-format the files named in the log instead of hand-fixing each line.
- Pin formatter versions in the project so local and CI stay in sync.
