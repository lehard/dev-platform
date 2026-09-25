# Design

Normalize direct handoff into a one-child execution envelope at the supervisor boundary, retaining the original canonical handoff for materialization. Use the existing managed child start and finish path for N=1. After exact child merge and archive on main, reconcile the parent from the complete set of linked children and their authoritative terminal evidence; close the parent only after Project Done succeeds. Keep the shared candidate path for N>=2 and apply the same parent reconciliation proof after its merge. Reconcile older parents with this idempotent terminal operation. Cleanup uses exact task and generation identity after terminal proof.

## Risks

- Premature parent closure: verify every linked mandatory child, Issue closure, archived provenance and merged delivery before Done.
- Stale handoff or overwritten worktree: validate source binding and use existing admission/worktree guards.
- Downstream drift: update template docs with central docs and test rendered behavior.
