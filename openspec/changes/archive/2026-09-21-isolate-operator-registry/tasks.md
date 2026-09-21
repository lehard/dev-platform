# Tasks

## 1. Provision the private operator repository
- [x] Create the private operator repository and seed it with an empty registry.
- [x] Set `DEV_PLATFORM_OPERATOR_REPOSITORY` on `lehard/dev-platform`.

## 2. Fix the three workflows
- [x] `adopt-project.yml`: fail closed on missing operator repository config; mint a contents-write token scoped to it; check it out; promote against `operator/managed-projects.json`; commit/push there instead of `platform/`.
- [x] `rollout.yml`: fail closed on missing operator repository config; mint a contents-read token scoped to it; check it out; validate/build the matrix against `operator/managed-projects.json`.
- [x] `reconcile-stale-rollouts.yml`: same read-only pattern as `rollout.yml`.

## 3. Documentation
- [x] `docs/managed-rollout.md`: document the private-repository CI resolution mechanism and the new repository variable.
- [x] `docs/operator-config.example.toml`: note that `registry_path` may point at a local clone of the private operator repository.

## 4. Verify
- [x] Update workflow-content contract tests for the new path/token step; assert `platform/managed-projects.json` no longer appears.
- [x] Full test suite green.
- [x] Verify source/template parity and semantic OpenSpec completion.
