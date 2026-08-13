# Proposal: Reconcile squash-merged scope claims

## Why

The multi-agent scope gate can keep treating a sibling task as active after its exact PR was squash-merged, because local branch-ancestry detection does not survive squash merges. That stale claim can block otherwise safe validation/publication work.

## What Changes

- Reconcile managed board activity against exact authoritative PR merge state before hard scope gating.
- Treat proven terminal squash-merged siblings as completed for claim purposes even without feature-branch ancestry.
- Keep ambiguous or unavailable state fail-closed and never mutate another task worktree.

## Impact

- Modified specifications: `worktree-coordination`, `platform-lifecycle`.
- Expected surfaces: agent-board status/reconciliation, scope gate, publication identity lookup and focused concurrency tests.
