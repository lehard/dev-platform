## Context

`start_managed_task.py` imports `start_task.py`; its current import graph loads
`rollout_preflight.py`, which imports `PrRef` and merge helpers directly from
`project_publish.py`. In a project-owned harness, Copier deliberately preserves
that file and it need not expose the platform harness API. Jara_Fin therefore
failed before the normal managed-start transaction could establish canonical
state.

## Design

1. Make the managed-start import graph independent of project-owned
   publication modules for `harness_mode=project`. Shared lifecycle data types
   and exact-head operations used by platform-owned reconciliation belong in a
   platform-owned module, or are loaded only inside a proven
   platform-owned-only operation.
2. Keep pending-rollout observation available to all harness modes without
   importing project-owned code. A mutation requiring platform publication
   remains explicitly gated by the platform harness mode and fails closed if
   its platform-owned dependency is unavailable.
3. Test the real entrypoint with a minimal Jara-shaped fixture: valid managed
   package, `harness_mode=project`, and a preserved `project_publish.py` that
   lacks `PrRef`. Assert standard start creates only the normal task-owned
   state and does not use a project-specific workaround.
4. Retain a platform-mode fixture proving the exact pending-rollout merge
   preflight still sends an exact PR identity/head to its platform-owned
   publication implementation.

## Failure handling

No compatibility fallback may fabricate `PrRef`, import arbitrary symbols from
the downstream project, or update the source Issue/Project status before
admission succeeds. An unavailable platform-owned dependency reports a bounded
actionable error with no worktree, board, or status side effect.

## Alternatives considered

- Require every project-owned `project_publish.py` to implement the platform
  API. Rejected: it breaks the declared ownership boundary and makes Copier
  adoption depend on uncontrolled downstream edits.
- Keep the Jara workaround as a documented alternative start path. Rejected:
  it bypasses the managed lifecycle and leaves task status/provenance
  reconciliation incomplete.
