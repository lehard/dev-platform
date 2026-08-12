## Why

Source backlog issue: `lehard/development-backlog#19`  
Prepared against: `lehard/dev-platform@5eb43498ec0ba996932adf9d0a46d1df5993e29a`

`lehard/dev-platform#178` recorded a full implementation and validation cycle that had to be repeated after the task was discovered stale against `origin/main`. The platform already synchronizes integration state before task start and checks remote state again near publication, but that leaves a long gap in which main can advance while expensive implementation and full validation proceed on a branch that will need reconciliation anyway.

The missing behavior is a cheap freshness boundary, not a new synchronization or caching subsystem.

## What Changes

- Add a deterministic remote-main freshness observation to platform-owned task execution.
- Re-check task-head ancestry against freshly observed remote main immediately before expensive full/protected validation.
- Stop before the expensive validation set when the task is stale/diverged and return a clear resumable rebase/reconciliation-first outcome.
- Preserve existing no-force-push, protected-main, exact-head and publication semantics.
- Do not add validation receipt reuse/caching; `dev-platform#173` remains a separate optimization.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: task execution must establish fresh authoritative base ancestry before using expensive validation as delivery evidence.

## Impact

The implementation should reuse existing fetch/ancestry primitives and current validation entrypoints where possible. The exact hook before full validation is intentionally left to implementation preflight because validation may be entered through more than one lifecycle path.
