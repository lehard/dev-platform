## Why

Source backlog issue: `lehard/development-backlog#16`  
Prepared against: `lehard/dev-platform@3c970b815b92f0711d85957a263330b8ecd9d439`

`lehard/dev-platform#154` recorded publication continuing while the integration checkout already contained uncommitted copies of the task result; the conflict was discovered only after GitHub had merged the PR. Related friction `#135` showed task-related changes remaining directly in integration/main. The current lifecycle serializes post-merge reconciliation but does not re-check integration cleanliness at the last safe point before remote merge intent is armed.

## What Changes

- Re-observe integration checkout state immediately before ordinary merge, native auto-merge or merge-queue enrollment.
- Fail closed before remote merge mutation when local integration contains divergent uncommitted state; never auto-stash/reset/clean it.
- Re-check under the existing integration serialization boundary so state that changed while PR checks were pending is visible.
- After an already-confirmed remote merge, preserve GitHub authority and allow only bounded content-equivalence-safe reconciliation; divergent local content remains a blocker.
- Keep exact-head publication recovery and idempotent retry semantics.

## Capabilities

### Modified Capabilities

- `platform-lifecycle`: add the last-safe-point integration-state guard before protected remote merge.
- `publication-recovery`: classify already-merged local reconciliation against equivalent versus divergent integration content without redefining the confirmed remote merge as failure.
