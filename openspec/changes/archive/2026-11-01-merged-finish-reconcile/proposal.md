## Why

For merged PR #829, `finish` in its worktree first refused on the board scope gate, because the claim had been released at admission. After the claim was restored by hand, `finish` entered developer handoff: the worktree was at a pre-finalize head with an active change, and `finish_task.main` checks `managed_candidate` before it checks whether the PR is merged.

## What Changes

- `finish_task.main` observes the exact PR of the branch first. When it is MERGED, finish goes to the existing post-merge reconcile path before the managed-candidate handoff branch.
- The lifecycle preflight board-claim condition does not apply to that merged reconcile.

## Capabilities

### Modified Capabilities

- `completion-lifecycle`: finish of a merged PR reconciles before any developer handoff.

## Impact

`template/scripts/finish_task.py`, `lifecycle_preflight` board condition, tests. Coordinator decision, 2026-11-01.
