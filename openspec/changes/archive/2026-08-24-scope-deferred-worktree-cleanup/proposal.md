# Proposal: Scope deferred worktree cleanup

## Why

Routine housekeeping for one completed task can currently process unrelated deferred worktrees because the documented cleanup entrypoint is global by default. A task-local recovery action must not mutate another agent's state.

## What Changes

- Make normal deferred cleanup target one exact task/worktree identity.
- Require an explicit `--all` for global cleanup.
- Preview bounded global candidates before mutation.
- Keep existing safety/idempotency checks and fail closed on ambiguous/stale identity.
- Make finish output the exact targeted recovery command.
