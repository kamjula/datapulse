# CI Failure: Syntax or Import Error

## Symptoms
- `SyntaxError` or `IndentationError` with a file and line number.
- `ModuleNotFoundError` / `ImportError` at collection or startup time.
- Tests fail before running a single test: `errors during collection`.

## Likely cause
- A typo or bad merge left invalid syntax in a file the change touched.
- Code imports a package that is used locally but missing from requirements.
- A renamed module was not updated at every import site.

## Fix
- Open the file and line named in the traceback; it is usually exact.
- If an import fails, add the package to requirements rather than removing the import.
- Run the test collection step locally (`pytest --collect-only`) before pushing.
