# Tasks

- [x] Add `scripts/rollout_failure_streak.py` with `record-failure`/`record-success` subcommands, durable state parsed from a GitHub-issue HTML-comment marker, exact-repository-slug matching, and fail-closed handling of an unparseable prior state.
- [x] Increment `consecutive_failures` on each terminal blocked attempt and reset (close the tracking issue) the next time that project's rollout preparation succeeds.
- [x] Escalate at `consecutive_failures >= 3`: label the tracking issue `rollout-alert` and emit a `::warning::` workflow annotation naming the project, streak length, and issue URL.
- [x] Wire both subcommands into `.github/workflows/rollout.yml`: add `issues: write` to top-level permissions, call `record-failure` after the existing diagnostic-artifact-upload step, call `record-success` after a successful `prepare`, both `continue-on-error: true` and scoped to the existing `steps.pending.outputs.found != 'true'` guard.
- [x] Ensure a tracking-layer failure never changes rollout's own exit status, pushes, merges, or affects PR-creation conditions.
- [x] Add regression tests for streak increment/reset/threshold-escalation, exact-slug matching, and fail-closed unparseable-state handling.
- [x] Add workflow tests asserting the new permission, step conditions, and non-interference with existing push/PR-creation conditions.
- [x] Update `docs/managed-rollout.md` with the failure-streak alert mechanism and threshold.
- [x] Re-run platform CI/OpenSpec validation and semantic verification on the exact final implementation.
- [x] Record `OpenSpec-Verify: PASS` plus verification method for this change and archive it.
