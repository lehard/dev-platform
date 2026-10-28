## 1. Release-level alarm

- [x] 1.1 Add `scripts/rollout_alarm.py`: read the current run attempt's jobs and failed-job annotations, classify plan and per-project failures, create or comment on one `rollout-alert` issue per release tag, note success on an open issue, fail non-zero on any delivery failure.
- [x] 1.2 Add the final `alarm` job to `.github/workflows/rollout.yml` (`needs: [plan, rollout]`, `if: always()`, workflow-ref checkout, `actions: read`, `checks: read` and `issues: write`, no `continue-on-error`), passing event, triggering actor, requested version and repository.

## 2. Streak tracker fails explicitly

- [x] 2.1 Remove broad exception swallowing from `record-failure`, `record-success` and `reconcile`; require `ROLLOUT_PROJECT_TOKEN` in `reconcile`; make the `rollout-alert` label description generic.
- [x] 2.2 In `rollout.yml` run the failure step only when preparation failed, require the diagnostic file, and drop `continue-on-error` from both streak steps; drop it from the alert step of `reconcile-stale-rollouts.yml`.

## 3. Docs and verification

- [x] 3.1 Update `docs/managed-rollout.md` (alarm, both dispatch paths, failure semantics).
- [x] 3.2 Tests: alarm for plan failure (auto-dispatched and manual), partial per-project failure, cancelled job, success without and with an open alarm issue, missing annotation, delivery failure; streak commands propagate failures; workflow structure for the `alarm` job and streak steps.
- [x] 3.3 Run full validation and semantic OpenSpec verification.
