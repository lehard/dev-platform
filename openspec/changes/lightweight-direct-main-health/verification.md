# Verification: keep direct-mode main health lightweight

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review using repository artifacts, the Cuby v1.4.7 post-merge failure, and GitHub Platform CI #235

## Completeness

- The observed Cuby failure is covered directly: generic direct-mode main CI no longer executes the configured full project check set.
- Pull-request selected checks, direct-main lightweight health, and manual full dispatch are all represented in template behavior, documentation and tests.
- Project-owned harness behavior is unchanged.

## Correctness

- PR events still execute selected checks when Dev Platform owns the harness.
- `workflow_dispatch` is now the only event that executes `scripts/select_checks.py --full --execute` in generated platform-owned CI.
- Direct `main` push still runs checkout, platform doctor, OpenSpec lifecycle hygiene and strict OpenSpec validation, but skips the full selector step.
- This removes the dependency-installation failure that occurred on Cuby main (`pytest` missing) without weakening its pre-merge PR gate.

## Coherence

- The implementation matches the local-heavy/cloud-final policy: required full verification happens before publication, direct main is a lightweight health signal, and manual dispatch is the deliberate full cloud path.
- No arbitrary project dependency installation was added to the generic workflow.
- Existing PR compatibility and concurrency cancellation remain intact.

## Acceptance evidence

Platform CI #235 passed on head `dbd2a8ba1653a02d36d8219af34c1e36ee35016a`, including unit tests, strict OpenSpec validation, factory renders, Copier upgrade smokes, mature project harness adoption and project-harness smart-update fallback.

No CRITICAL or WARNING findings remain. Ready for archive and patch release.
