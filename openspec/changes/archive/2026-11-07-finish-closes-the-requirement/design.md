## Context

`reconcile_linked_parent` in `finish_task.py` runs after `MERGED` and local reconciliation. `reconcile_parent` in `requirement_terminal.py` holds all proof checks and is reused unchanged. `cleanup_completed_task` defers when the caller's cwd is the task worktree, which is the normal case.

## Decisions

**One observation.** `parent_closure(root, child)` in `requirement_terminal.py` reads the parent and returns its reference, state and what is missing, or `None` without a parent. It reads only: Issue state, the other children's Project status, operator acceptance and the retrospective. The child being delivered is excluded from the open children, so the same function serves before publication, after the merge and in `status`. An unreadable child status raises.

**Closure.** `close_after_delivery(root, child)` uses that observation: closed and waiting children return a message; otherwise `reconcile_parent` runs with `merged_children={child}` and its own checks decide. `finish` wraps any failure into a non-zero exit that states the merge stands, the cause, and the retry `python3 scripts/finish_task.py --cleanup` in the task worktree. The retry path already skips publication for a merged PR, and cleanup runs after closure, so the worktree still exists.

**Notice.** After validation and before publication, `finish` prints each missing item for a managed child. It stops nothing.

**Status.** `run_status` adds a `requirement` obligation: `pending` with the missing items, `warning` while other children are open.

**Cleanup.** `_cleanup_deferred_completed_tasks` gets a `skip` path. `finish` calls it after its own cleanup, excluding its own record, and prints each removed path and each kept record with its reason and exact command. A failure there is a warning, as for its own cleanup.

## Risks

A merged child can exit non-zero until the retrospective exists; that is intended. A kept record stays until a later `finish`.
