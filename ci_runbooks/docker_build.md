# CI Failure: Docker Build

## Symptoms
- `docker build` fails with a step error like `executor failed running`.
- `failed to solve` or a Dockerfile line number in the error.
- Base image pull errors: `manifest unknown` or `pull access denied`.

## Likely cause
- A command inside the Dockerfile fails (install, copy path, missing file).
- The base image tag was removed or renamed upstream.
- The build context is missing a file the Dockerfile expects (check .dockerignore).

## Fix
- The log names the Dockerfile step that failed; reproduce that step locally.
- Pin base images to a digest or a stable tag instead of `latest`.
- Check that copied paths exist in the build context and are not dockerignored.
