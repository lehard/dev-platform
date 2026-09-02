# Design: One PR identity across continuation and completion

## Decisions

1. Before pushing, prove the remote branch is the exact head of the expected open PR and is an ancestor of local HEAD.
2. Fast-forward only that branch, then re-read PR identity and reconcile current main using normal merge history.
3. A remote change during either proof aborts without force.
4. Exact `MERGED` state is terminal: synchronize integration main and managed status, never create a new task head or PR.
5. Existing publication and terminal-reconciliation modules remain authoritative.
