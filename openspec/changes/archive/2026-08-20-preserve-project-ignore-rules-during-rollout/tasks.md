# Tasks

## 1. Define the preservation boundary

- [x] 1.1 Inspect the current template/Copier ownership of `.gitignore` and encode one deterministic platform-baseline + project-extension contract.
- [x] 1.2 Update the platform-rollout OpenSpec delta before implementation if the concrete mechanism changes the agreed behavior.

## 2. Implement rollout protection

- [x] 2.1 Change new-project render and existing-project Copier update behavior so project-owned ignore extensions survive repeated platform releases.
- [x] 2.2 Add a fail-closed rollout check for loss of effective ignore coverage caused by managed rendering, using synthetic representative secret/runtime artifact classes.
- [x] 2.3 Keep the guard read-only with respect to downstream local artifacts: never delete, stage or commit files surfaced by a failure.

## 3. Regression and release

- [x] 3.1 Add a Cuby-like regression fixture covering `.env`, provider credentials, DB, dependency/build and TypeScript state classes without embedding project secrets.
- [x] 3.2 Run relevant rollout/Copier/template tests plus the repository's required validation and semantic OpenSpec verification.
- [x] 3.3 Complete the normal archive/publication lifecycle and issue an immutable patch release so managed projects can receive the repair.
