## Context

- `execute_integration_repair` already merges main in a disposable checkout and calls the writer only when conflicts exist or the red gate is `required-checks`; otherwise the harness alone commits the merge (#730's actual repair).
- `hosted_workers.UNHOSTED` refuses `integration-repair` because its job may hold a writer and a provider token; `work-next --run` with `integration-repair` requires `--llm-command`.
- After BR-768/T1 an environment failure of the derived merge is a queue error; the remaining derived-merge failures are candidate reasons.

## Decisions

- **A kind, not a mode.** `integration-merge` is a separate job kind so a hosted class can claim it without ever being able to claim a writer job; the containment basis of `UNHOSTED` stays intact for `repair` and `integration-repair`.
- **Same state and bound.** The candidate state stays `integration-repair-pending` and attempts count under `integration-repair`, so overview, labels, readmission and the block after `MAX_INTEGRATION_REPAIRS` are unchanged. The merge-only round is recorded in the red gate (`merge_only: true`), the one field already persisted with the round; the job republish, validated-push recovery and the repair attention read it.
- **Criterion is the trial merge.** The queue offers it only for the `integration` gate with an empty `merge_conflicts(head, current main)`. Conflicts (ordinary or derived-only that the derived merge could not resolve), a red required check and a refused GitHub branch update keep integration repair.
- **No writer inside the kind.** The executor refuses to call a writer; conflicts or a `required-checks` gate at execution time fail the job with the conflicting paths. The existing failure path records the next attempt as `integration-repair` (writer, escalated to the operator by T1) or blocks at the bound. This is the lifecycle's next step, recorded and visible, not a silent substitute.
- **Enablement is an owner step.** The class exists in the plan table; the hosted workflow runs it only once the owner adds `integration-merge` to `DEV_PLATFORM_HOSTED_KINDS`.

## Risks

- A plain merge after a failed derived merge leaves derived files merged textually; required checks on the integrated head still gate the merge, and a red check becomes integration repair.
