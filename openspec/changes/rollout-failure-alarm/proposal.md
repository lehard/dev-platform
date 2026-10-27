## Why

A failed managed rollout is silent. `publish-version.yml` dispatches `Roll Out Platform` fire-and-forget, and the only durable signal, `scripts/rollout_failure_streak.py`, runs inside the per-project job after rollout preparation:

- a failed `plan` job (v2.0.0, run 40469918454: operator registry checkout "repository not found") records nothing anywhere;
- a per-project job that fails before platform tooling is checked out (v1.12.0, run 39962648272: GitHub App not installed for one target) runs the streak step against a script that is not there yet, and `continue-on-error` hides that;
- the `rollout-alert` label is added only at the third consecutive failure;
- the tracker itself turns every error into a warning (`except Exception: return 0` plus `continue-on-error`), as the accepted spec scenario "The tracking layer itself fails" requires.

The owner asked (lehard/development-backlog#832) that a failed project update after a release raises an explicit alarm, and that the alarm path fails loudly when it cannot be delivered. Since 2026-10-27 managed rollout is not auto-dispatched (`DEV_PLATFORM_MANAGED_ROLLOUT_ENABLED=false`); rollout runs by manual dispatch, so the alarm covers both the release-dispatched and the manually dispatched path.

## What Changes

- New final job `alarm` in `.github/workflows/rollout.yml`: `needs: [plan, rollout]`, `if: always()`, no `continue-on-error`, workflow-ref checkout, default `GITHUB_TOKEN` with `actions: read`, `checks: read` and `issues: write`.
- New `scripts/rollout_alarm.py`: reads the current run attempt's jobs and the failure annotations of each failed job through the GitHub API, and:
  - on any failed, cancelled or timed-out job (plan or per-project), opens one issue per release `Managed rollout failed: <tag>` labeled `rollout-alert`, or comments on the open one, naming the tag, each failed stage or target repository, its failed step and error text, the run link and dispatch context (event, actor, requested repository);
  - on a fully successful run raises no alarm; if an alarm issue for that tag is already open it adds a success note for the run's scope and leaves the issue open (one run does not prove every listed target recovered);
  - fails non-zero, naming what failed, when it cannot read the run or create, comment on or label the issue.
- `scripts/rollout_failure_streak.py`: `record-failure`, `record-success` and `reconcile` no longer catch every exception; a GitHub or state error exits non-zero with its message. `reconcile` requires `ROLLOUT_PROJECT_TOKEN` instead of treating its absence as "not recovered". Unproven recovery still leaves the alert open without failing.
- `rollout.yml` streak steps: no `continue-on-error`; the failure step runs exactly when rollout preparation failed (`steps.prepare.outcome == 'failure'`) and requires the preparation diagnostic instead of substituting `unknown`.
- `reconcile-stale-rollouts.yml`: the alert reconciliation step drops `continue-on-error`.
- The `rollout-alert` label description becomes generic ("Managed rollout failed and needs human attention").
- MODIFIED requirement "Repeated managed rollout failures against the same project are surfaced to a human": the accepted "strictly additive, failure is only a warning" behavior is replaced by an explicit failure of the tracking step. ADDED requirement for the release-level alarm.
- `docs/managed-rollout.md` describes the alarm and the changed failure semantics.

## Impact

- `.github/workflows/rollout.yml`, `.github/workflows/reconcile-stale-rollouts.yml`, `scripts/rollout_alarm.py` (new), `scripts/rollout_failure_streak.py`, `docs/managed-rollout.md`.
- Tests: `tests/test_rollout_alarm.py` (new), `tests/test_rollout_failure_streak.py`, `tests/test_rollout_failure_streak_workflow.py`.
- Spec: platform-rollout.
- Platform-repository operator surface only; nothing under `template/` changes, so downstream projects are unaffected.
- Behavior change for operators: a tracker failure now turns the per-project rollout job or the daily reconciliation red instead of a warning.
