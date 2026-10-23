## Why

`agent_friction.ambiguous_attribution_events` treats every recent task-less event in the global log as ambiguous, and the coordinator's automated task and Requirement retrospectives block on it. An event recorded from an integration checkout about something unrelated (on 2026-10-22, an incident in another project) stopped the post-merge retrospectives of two unrelated candidates until an operator ran `attribute` by hand; about seven such stops happened in two weeks. Meanwhile the manual checkpoints only print the same ambiguity as a warning and record `none` anyway, so the manual and automated paths disagree.

The owner chose variant A: an event inside a task worktree belongs to that task; an event outside a task is marked as not related to any task and never blocks other retrospectives.

## What Changes

- `record` outside a task (main/integration checkout, detached or unknown branch, no explicit `--task`) stores `attribution: "no-task"` instead of `unattributed`. Inside a task worktree it keeps the current branch attribution.
- A legacy task-less event with no other attribution evidence whose recorded branch is a non-task name is read as `no-task`; the stored event is not rewritten.
- `agent_friction.py attribute --id ID --no-task --reason TEXT` appends an explicit no-task attribution. An explicit no-task and an explicit task attribution of the same event conflict and fail. An automatic `no-task` can still be attributed to a task explicitly.
- `ambiguous_attribution_events` returns only task-less events with no usable branch, source issue or attribution and not `no-task`.
- The manual `agent_friction.py checkpoint` and `requirement_retrospective.py checkpoint` refuse, before writing a receipt, when ambiguous events exist, naming the ids and both `attribute` forms, the same as the automated retrospectives.
- `review-path` and checkpoint output list recent `no-task` events (id, reason when explicit) as informational; they are not mandatory signals of the task under review.

## Impact

- `template/scripts/agent_friction.py`, `template/scripts/requirement_retrospective.py`; `template/scripts/integration_contour.py` keeps its blocking call and gains no-task-aware selection through the shared function.
- Spec: platform-lifecycle ("Friction events carry resolvable task attribution").
- Docs: `docs/engineering/agent-workflow.md` friction section.
