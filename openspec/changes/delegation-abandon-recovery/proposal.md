## Why

When the supervisor of a delegated Codex child is killed, `execution_plan.delegation` stays open. `escalate`, `approve-supervisor-diff` and `prepare` all refuse, so a coordinator has to re-point the routing record by hand. `route-codex` also does not say that on R2 the child is the writer.

## What Changes

- `model_routing.py close-abandoned-delegation --reason TEXT` closes an open Codex delegation only when no process other than the caller's own ancestry runs in the assigned worktree.
- The closure records outcome `abandoned`, the observation and the post task content; it records no execution.
- `prepare` accepts a route whose delegation is closed as abandoned; the history stays.
- `route-codex` prints the writer for the selected tier.

## Impact

- `template/scripts/model_routing.py`, `scripts/dogfood_task.py`, `docs/engineering/model-routing.md`, tests, manifest.
- Spec: model-routing.
