## Why

`start_task.py` calls `reconcile_pending_rollout`, which merges a green pending Dev Platform rollout PR and fast-forwards local `main` before any task branch exists. The session has no channel to say "do not roll out now". A user's explicit prohibition in the session was therefore violated at task start: the pending rollout PR was merged anyway, and only afterwards did the user accept the result. A start that mutates shared state against an explicit prohibition is a constraint violation, not an inconvenience. The merge is also silent until after it has happened.

## What Changes

- One explicit deferral channel: environment variable `DEV_PLATFORM_DEFER_ROLLOUT=1`, plus a `--defer-rollout` flag on `start_task.py`, `start_managed_task.py`, `execute_managed_task.py` and `execute_requirement.py advance` that sets the same variable for the process and its children. Any other non-empty value is an explicit error.
- While deferred, `reconcile_pending_rollout` only observes: it neither merges, closes, relabels nor synchronizes anything, and returns a `deferred` result naming the pending PR, its observed state and the reason. `start_task` prints it and continues; task start does not fail because a rollout is pending.
- Without a deferral the behavior is unchanged except that, immediately before the merge, start prints a preflight line naming the PR, its version, the merge and the local `main` synchronization it is about to perform and how to defer it. `agent_doctor.py`, which start already runs first, reports a green pending rollout as "will be merged by the next task start" with the same instruction.
- Docs and the rendered `AGENTS.md` tell an agent to start with the deferral whenever the user prohibits rollout in the session.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: "New work reconciles an authoritative pending platform rollout first" gains the session deferral and the pre-merge announcement.

## Impact

`template/scripts/rollout_preflight.py`, `template/scripts/start_task.py`, `template/scripts/start_managed_task.py`, `template/scripts/execute_managed_task.py`, `template/scripts/execute_requirement.py`, `template/scripts/agent_doctor.py`, `template/AGENTS.md.jinja`, `docs/engineering/agent-workflow.md` and tests. Downstream projects receive it through the normal release rollout; `harness_mode=project` repositories keep their own adoption path and are unaffected.

## Non-goals

Changing the mandatory rollout policy for sessions without a prohibition; weakening required checks or adding any bypass; other start-time mutations (there is no other shared-state mutation in start today); other findings of the originating review.
