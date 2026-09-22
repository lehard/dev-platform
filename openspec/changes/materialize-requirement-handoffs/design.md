# Design: Idempotent handoff materialization

## Identity and transaction boundary

The handoff digest and parent Requirement identify a materialization attempt. The adapter validates source bindings, renders the managed bundle, and asks the existing managed-task intake to create or exactly reuse the Issue. It records no competing state: authoritative Issue metadata and the Requirement body link are reread on each retry.

## Retry behavior

If Issue creation succeeds but parent linkage fails, the retry resolves the exact child by its immutable handoff identity and repairs the link. If multiple candidates or mismatched provenance are found, it stops with an actionable error. Success is returned only after both the child and bidirectional linkage are confirmed.

## Boundary

The resulting child enters the normal `start_managed_task.py` / OpenSpec lifecycle. The parent retains business context and derives progress from its children.
