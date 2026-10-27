## Developer re-admission from integration-repair-pending

`_supersession` already proves: the latest trusted record is bound to the proven head, the handoff names the same task, the offered job has no live claim, and the new head descends from the proven head. For `integration-repair-pending` the proven head is the integrated head (the coordinator's `update` after merging `main`). Adding the state to `READMISSION_STATES` reuses all of these refusals. It is not a finding-level state, so content need not change for the supersession itself; the archived re-handoff still requires a re-recorded semantic receipt.

The published integration-repair job is head-bound to the proven head. After the superseding admission the newest record is the developer's review-pending record, so `build_job` no longer derives the integration-repair job; a writer that claims the old job afterwards is discarded because `run_claimed_integration_repair` refuses a job that differs from the derived one.

`_awaiting_readmission` uses the same set: a pushed descendant head in `integration-repair-pending` is shown as awaiting developer re-admission. A writer push is followed by its `update` comment, which makes the pushed head the proven head, so it is not mistaken for a developer head once recorded.

### Archived managed task

Finalize archives the change before integration, so the developer's task is archived. `pr_review_gate.archived_readmission` calls `publication_queue.semantic_readmission`, which calls `local_status`. Today `local_status` raises when the local head is neither the admitted nor the proven head and is not already pushed. New rule in `local_status`: when the latest trusted record at the proven head is `integration-repair-pending` and the local head strictly descends from the proven head, return `state: readmission` with `proven_head`. `semantic_readmission` accepts the lineage `blocked-retryable` + `semantic-verification` as today, or `integration-repair-pending`. Any other state keeps today's behaviour. A non-descendant local head keeps the explicit `local task head is not the admitted or proven coordinator head` refusal.

## Failed-check evidence

`required_check_state_for_ref` returns the failed rows with `name`, `state`, `workflow`, `link`. The queue raises `IntegrationRepairNeeded` with an extra structured `failed_checks` list; `_integration_repair` stores `red_gate.evidence` as `{"detail": <message>, "failed_checks": [...]}` for the required-checks gate. Other gates keep their string evidence.

The writer brief is built on the operator node (`run_claimed_integration_repair`), which has `gh`. For a `required-checks` red gate:

1. `failed_checks` must be a non-empty list of rows with a name and an Actions job link `https://github.com/<owner>/<repo>/actions/runs/<run>/job/<job>`; otherwise refuse.
2. For each, `gh run view <run> --job <job> --log-failed -R <repo>`; a non-zero exit or empty output refuses, naming the check and gh's message.
3. The brief keeps the last 80 lines, at most 6000 characters, per check under `failed_checks[].log_excerpt`.

The refusal is a `WorkerError` raised before the writer launch and outside the attempt-spending `fail` path: work-next releases the claim and reports the error, exactly like other run failures, without spending an integration-repair attempt. A `merge_only` integration merge and a conflict-only integration repair are unchanged.

## Not changed

Attempt limits, review, merge semantics, writer start (operator-run), the merge-only route.
