## Why

Re-admission exists only for managed handoffs. A quick task with a failed required CI stops at a `finish` refusal and a coordinator decision, which once led to closing a PR and publishing it again around the rules. The fix belongs in the queue, so the same PR continues.

## What Changes

- `finish` on the same PR supersedes the admitted head of a quick task with a descendant head, under the checks a managed supersession already uses. The new head returns to `ready` without review.
- `status` and `next_action` name the developer path at each step of a red CI for a quick task. "Coordinator decision" goes away for this case.
- `reconcile` keeps its merge local for an admitted quick candidate. Only `finish` moves that head, and it records the transition in the same run.
- A head without a recorded transition never integrates or merges.

## Impact

- `template/scripts/publication_queue.py`, `template/scripts/task_reconciliation.py`, status output in `template/scripts/finish_task.py`, tests, `docs/engineering/agent-workflow.md`, manifest.
- Managed re-admission keeps its behavior. Portable projects keep their reconcile and never load the coordinator stack.
