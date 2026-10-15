# CI Failure: Dependency Resolution

## Symptoms
- `Could not find a version that satisfies the requirement` in the install step.
- `ResolutionImpossible` or `No matching distribution found` from pip.
- npm errors like `ERESOLVE unable to resolve dependency tree` or yarn `Couldn't find any versions`.

## Likely cause
- A pinned version was yanked or never existed for this Python/Node version.
- Two packages in the requirements file want conflicting versions of a shared dependency.
- The lock file is stale after a requirements edit.

## Fix
- Check the exact package and version named in the error against the index.
- Loosen the conflicting pin or align both packages to a compatible range.
- Regenerate the lock file locally, commit it, and re-run the install step.
