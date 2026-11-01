## Why

After merge, PR #822, #823, #825 and #829 (direct managed tasks of BR-799) blocked terminal reconciliation three times with "cannot resolve the task's source Issue". `resolve_lineage` understands only BR branch identity. A direct task records only an opaque `private_lineage_handle`, which `source_issue_for_provenance` resolves only from the task worktree's local state. GitHub issue search over comments is incomplete: it misses the mapping of #948.

## What Changes

- `run_terminal` exits idempotently when a trusted lifecycle result already records a successful terminal reconciliation of this PR.
- Otherwise, for a managed candidate without BR identity, it reads the handle from the archived provenance at the merged head. A paginated GraphQL walk then reads the open private Backlog Issues with their comments. The walk has an explicit page cap: exceeding it is an error naming the count, never a partial result.
- Only mapping markers authored by a proven writer or the coordinator App count. Exactly one marker for the handle and change must be found, and `require_handle` must verify it. Then Project Done and Issue closure follow. If no open Issue carries the handle, the job stops with "no open Issue carries this handle (already closed or missing)".
- Logs and PR comments name only the verified Issue number, never the handle.

## Capabilities

### Modified Capabilities

- `publication-queue`: terminal reconciliation of a direct managed task.

## Impact

`template/scripts/integration_contour.py`, `private_lineage.py`, tests. Coordinator decision D1=B with conditions, 2026-11-01.
