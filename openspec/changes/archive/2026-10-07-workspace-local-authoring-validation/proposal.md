## Why

Work identity: BR-367/T1

Exact-target authoring validation currently creates a detached worktree in the system temporary directory. Attached local workspace policy rejects that checkout outside reviewed roots (process evidence lehard/dev-platform#302 and #316), preventing normal managed handoff materialization.

## What Changes

Keep exact prepared_against validation, but allocate its isolated helper-owned worktree inside the existing configured platform worktree storage of the integration checkout. Validate placement and ownership before creation; retain normal local source admission and shared-workspace checks. Replace ignored cleanup failures with explicit diagnostics and bounded identity-checked cleanup, including recovery after interruption.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `managed-task-intake`: exact-target validation placement and temporary-worktree cleanup.

## Impact

Shared template managed-task runtime, real-Git regression coverage and local workspace documentation. New projects receive the runtime through rendering; existing projects receive it through normal reviewed Copier updates. No machine paths, policy bypass, TMPDIR override, workspace manager or parallel task lifecycle.

## Success Evidence

Real Git with local workspace policy reproduces rejection of system-temp validation, then proves workspace-local exact-target validation works with unchanged TMPDIR, exact SHA and unchanged integration checkout. Success, validation failure, checkout-hook failure and interruption/recovery leave no unreported helper-owned worktree state; foreign and ambiguous paths fail explicitly.
