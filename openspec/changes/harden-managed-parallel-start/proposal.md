# Proposal: Harden managed parallel task start recovery

## Why

`lehard/dev-platform#262` reported that a new managed task could not enter an isolated worktree while an unrelated task had stale board/worktree state: `start_managed_task.py`'s multi-agent path had no durable, task-scoped identity recorded before worktree/board mutation, so a retry after any interruption could not reliably tell "this exact task is genuinely partial and safe to repair" apart from "this is unrelated sibling state I must not touch." The existing `Fresh managed start is isolated from stale integration task state` and `Managed task-specific state does not become shared authoritative identity` requirements already establish that unrelated task state must not be adopted or contaminate a fresh start, but they do not require a durable per-task transaction or bound the shape of safe recovery cleanup, which is what left this failure mode open.

## What Changes

- Persist a machine-local, per-change start transaction before any worktree/board mutation, locked so only repeated starts of the *same* managed change serialize; unrelated tasks stay independent.
- Recover only the exact registered worktree/branch/board entry named by that task's own transaction, and only when it has no unique commits, no unrelated dirty paths, matching task state, and provable exact Git-worktree registration.
- Never run global worktree/board pruning as part of managed-start recovery.
- Retire the transaction only after the start actually completes (resume or fresh creation); keep it on disk across an interruption so retry can resume safely.

## Impact

- Modified specification: `managed-task-intake`.
- Affected surfaces: `template/scripts/start_managed_task.py`, its regression suite (`tests/managed_start_transaction_cases.py`, `tests/managed_task_exact_state_cases.py`, `tests/test_managed_task_exact_state.py`).
- No change to the package/import/authoring contract, Project-status reconciliation semantics, or the CLI surface of `start_managed_task.py`/`managed_task.py`.
