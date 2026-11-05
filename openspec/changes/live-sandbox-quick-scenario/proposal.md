## Why

Every lifecycle dead end of recent deliveries was found on a live delivery while mocked unit tests stayed green. The queue has only ever run on this one public repository, so nothing proves a new queue change on real GitHub before it reaches main. A rendered project has no queue, so a test repository must run in source mode.

## What Changes

- A private sandbox repository carries an exact snapshot of the platform head over a small fixture project with its own fast CI and checks.
- It is isolated: own GitHub App, own operator configuration and registry, never in the production managed registry.
- Queue, worker, composition and absorb-main clones work on a private repository through the existing push credential mechanism.
- One runner command resets the sandbox and drives scenarios through documented entrypoints only.
- The first scenario drives a quick task to MERGED.

## Impact

- New runner under `scripts/` and `template/scripts/` as the source layout requires, fixture files, `docs/engineering/live-scenarios.md`, tests, manifest.
- `prepare_checkout` and its callers.
- Specs: new `live-lifecycle-sandbox`, `lifecycle-workers`.
