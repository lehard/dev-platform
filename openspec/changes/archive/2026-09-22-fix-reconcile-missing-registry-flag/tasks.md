# Tasks

## 1. Fix
- [x] `rollout.yml`'s `rollout` job: add its own operator-repository requirement, registry read token, and operator-registry checkout steps.
- [x] `rollout.yml`: pass `--registry operator/managed-projects.json` to both `reconcile` calls in the `rollout` job.
- [x] `reconcile-stale-rollouts.yml`'s `reconcile` job: add the same operator-registry checkout steps.
- [x] `reconcile-stale-rollouts.yml`: pass `--registry operator/managed-projects.json` to its `reconcile` call.

## 2. Verify
- [x] New regression tests asserting `--registry` is present at all three call sites.
- [x] Updated `create-github-app-token` pin-count assertion in `tests/test_managed_rollout.py`.
- [x] Full platform test suite green.
- [x] YAML parses for both workflow files.
