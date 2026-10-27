OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the rollout-failure-alarm platform-rollout delta, proposal, design and tasks; targeted unit and workflow-structure tests run during the change, with fixtures taken from the real failed run 40469918454; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner and coordinator decisions

- Owner request (lehard/development-backlog#832, 2026-10-27): a failed project update after a release raises an explicit alarm; the alarm path fails loudly.
- Coordinator decisions (2026-10-27): remove error swallowing from the streak tracker in the same MODIFIED delta, replacing the accepted "tracking failure is only a warning" behavior; cover both the release-dispatched and the manual dispatch path (managed rollout auto-dispatch is currently disabled); no demonstration run before merge, unit and structural tests are sufficient for the handoff.

## Implementation

- `scripts/rollout_alarm.py` (new): reads `actions/runs/{id}/attempts/{n}/jobs` and, for each failed job, its failure-level check-run annotations; reports `plan` by stage and per-project jobs by target repository; skipped jobs count as failures unless `plan` failed. It creates one `Managed rollout failed: <tag>` issue labeled `rollout-alert` or comments on the open one; on a successful run it only notes success on an open alarm and never closes it. Any read or write failure exits 1 with an `::error` naming it.
- `.github/workflows/rollout.yml`: final `alarm` job (`needs: [plan, rollout]`, `if: always()`, workflow-ref checkout, `actions: read`, `checks: read`, `contents: read`, `issues: write`, no `continue-on-error`). The streak failure step now runs on `failure() && steps.prepare.outcome == 'failure'`, requires `rollout-diagnostic.json` and has no `continue-on-error`; the recovery step has `set -euo pipefail` and no `continue-on-error`.
- `scripts/rollout_failure_streak.py`: the three `except Exception` wrappers are removed; `main` turns `TrackerError`/`OSError` into an `::error` and exit 1. `reconcile` requires `ROLLOUT_PROJECT_TOKEN`. The `rollout-alert` label description is generic.
- `.github/workflows/reconcile-stale-rollouts.yml`: the alert reconciliation step has no `continue-on-error`.
- `docs/managed-rollout.md` and Explorer node `copier-rollout` describe the alarm and the changed failure semantics.

## Completeness

- Plan stage fails: `test_plan_failure_opens_release_alarm_with_stage_step_and_error` (real run 40469918454 job/annotation shapes: stage `plan`, step "Checkout operator registry", "repository ... not found", unexpanded matrix job not listed, notice annotation excluded, duplicates collapsed).
- Release tag named before resolution: `test_plan_failure_before_version_resolution_names_release_from_version_file`.
- Partial failure and cancelled job: `test_partial_failure_lists_only_failed_targets`, `test_skipped_target_after_successful_plan_is_a_failure`.
- Both dispatch paths: the auto path (actor `github-actions[bot]`, all projects) and the manual path (actor `lehard`, one `repository`) in the two plan-failure tests; `test_alarm_job_passes_both_dispatch_paths_context`; `test_release_workflow_still_dispatches_the_same_rollout_workflow`.
- Later failing run for the same release: `test_later_failing_run_comments_on_the_open_alarm`.
- Successful run: `test_successful_run_raises_no_alarm`, `test_successful_run_notes_but_keeps_open_alarm`.
- Failed job without annotation: covered in the partial-failure test (log link, no invented text).
- Alarm cannot be delivered: `test_delivery_failure_fails_the_alarm`, `test_unreadable_run_fails_the_alarm`, `test_label_bootstrap_failure_propagates`, `test_main_exits_non_zero_naming_the_failure`; workflow structure `test_alarm_job_always_runs_after_plan_and_rollout`, `test_alarm_job_uses_workflow_ref_code_and_least_privilege_token`.
- Tracking layer fails explicitly: `test_missing_label_failure_fails_tracking_explicitly`, `test_cli_exits_non_zero_naming_the_tracker_failure`, `test_missing_project_token_fails_reconciliation`, `test_tracker_read_failure_propagates_from_reconciliation`, `test_script_entry_points_do_not_swallow_failures`.
- Missing preparation diagnostic: `test_failure_streak_step_runs_on_failed_preparation_and_fails_loudly`.
- Unchanged streak scenarios (first failure, increment, threshold, reset, no-op, unreadable state, label bootstrap) keep their existing tests.

All tasks in `tasks.md` are complete; 3.3 is this receipt together with the selected checks.

## Correctness and coherence

- `tests/test_rollout_alarm.py` (16), `tests/test_rollout_failure_streak.py`, `tests/test_rollout_failure_streak_workflow.py` and `tests/test_rollout_control_plane_regressions.py` pass (52 tests); the full repository test run is recorded in `automated-checks.json`.
- Nothing under `template/` changed; the platform manifest check passes.
- Limitations: the alarm is exercised with a fake `gh` and YAML structure assertions, not by a live GitHub Actions run; the coordinator deferred a demonstration run until after merge. `GITHUB_TRIGGERING_ACTOR` and the check-run annotations endpoint with `checks: read` were confirmed against GitHub documentation and the real run's API responses, not in a workflow run.
- Left unchanged and reported: `rollout_diagnostic.py ... || true` in the preparation step (the spec requires that step to keep its original exit code), and the streak CLI's `--tracker-repo` default (the workflows always pass it).
