## 1. Environment failure
- [x] 1.1 Add `RederivationEnvironmentFailed` and the pristine-main probe in `post_review_finalization`; classify a missing OpenSpec CLI and an unstartable command as environment failures.
- [x] 1.2 Map it to `QueueEnvironmentError` in the queue derived merge; re-raise it from `_integrate`; collect it in `worker` and end the run with `environment-error`.

## 2. Repair escalation
- [x] 2.1 Post the attention comment for `repair-pending` and `integration-repair-pending` from `_transition` with a repair-specific body naming the operator command.
- [x] 2.2 Update the repair placement row in `docs/engineering/hosted-lifecycle-workers.md`.

## 3. Verification
- [x] 3.1 Tests: generator failing on main and merged tree is an environment error with no repair job and a failed run; failing only on the merged tree stays integration repair; one repair attention per round, re-posted when lost.
- [x] 3.2 Run full validation and semantic OpenSpec verification.
