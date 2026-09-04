# Design: Bounded external-runtime compatibility pilot

## Decisions

1. **Reuse the existing runtime boundary.** The external-runtime contract introduced for the DeepSeek Harness work remains the integration seam. Ouroboros does not get a parallel adapter framework, task state or telemetry store.
2. **OpenSpec stays canonical.** Any Ouroboros Seed or other execution object is derived for one run from the exact task/OpenSpec revision. It is not independently edited and never becomes a second source of truth.
3. **Historical replay avoids production risk.** Reconstruct the pre-change repository state for backlog #94 and #30 and execute only in isolated pilot workspaces/worktrees. Current `main`, integration checkout and sibling worktrees are off limits.
4. **Do not pay for unnecessary duplicate native runs.** Use durable historical native execution/verification evidence when it is sufficient and comparable. Re-run the native arm only when a required comparison field cannot be established truthfully from existing evidence.
5. **Independent acceptance is authoritative.** Ouroboros terminal success/evaluation is execution evidence only. The replay result must pass the current Dev Platform verification/acceptance contract.
6. **Coupling is part of the result.** Translation code, lifecycle leakage, state duplication and manual intervention are measured as adoption cost, not hidden as pilot implementation detail.
7. **No half-adopted backend.** Temporary prototype/glue is removed after the pilot unless the final decision is `adopt-next-step` and the retained seam is demonstrably small, isolated and useful for the explicitly identified next step.
8. **Decision gate favors maintenance reduction, not novelty.** Ouroboros does not advance merely because it works. `adopt-next-step` requires correctness/reliability plus a concrete meaningful Dev Platform maintenance layer that could be removed or not built.
9. **Exact upstream identity.** The pilot records the exact Ouroboros release/commit and supported integration surface used; mutable `main/latest` is not the result identity.
10. **Failure is useful evidence.** If Ouroboros requires broad changes to task-intake/OpenSpec/verification/publication/rollout, cannot respect workspace ownership, or produces false-success/opaque recovery, stop rather than expanding scope.

## Decision outcomes

- `adopt-next-step`: both replay cases pass Dev Platform acceptance, no silent-success class appears, intervention/coupling are acceptable, and at least one substantial maintenance responsibility can be retired or avoided.
- `watch-only`: integration is technically viable but produces no meaningful substitution benefit yet, or upstream maturity is insufficient for a next adoption step.
- `reject-for-now`: reliability, correctness, containment or coupling is unacceptable; record the concrete evidence and an event/evidence-based revisit condition.
