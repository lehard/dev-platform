# Proposal: Roll back empty managed-start transactions

## Why

A package-validation failure can clean up every task-side effect but leave a `creating` transaction that rejects the corrected package revision. Safe retry should not require editing machine-local state.

## What Changes

- Remove a transaction when start fails before any worktree, branch or board mutation.
- Allow recovery to supersede an old empty transaction after proving those side effects are absent.
- Preserve fail-closed behavior for every partial or ambiguous state.
