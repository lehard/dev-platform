## Context

`enforce-managed-task-provenance-completeness` introduced a root-level `.managed-task-state.json` marker so a managed task remains recognizable when canonical OpenSpec provenance is missing. The guard is correct for genuine resume, but the marker currently survives into integration `main`. Because a fresh managed task is created from integration state, the new checkout inherits another task's marker before its own OpenSpec package is materialized. `import_task` sees `existing_state` and calls canonical provenance resolution for the requested new task; that resolver correctly fails because the new canonical change does not exist yet. A resume guard has therefore leaked into fresh-start semantics.

The same underlying ownership ambiguity already appears later in the lifecycle: after merge, reconciliation may inspect integration main and rediscover another task's identity. The fix should establish one rule across both boundaries: task-specific identity belongs to the exact task, not to shared integration state.

## Decisions

### Distinguish fresh start from genuine resume before provenance enforcement

Fresh materialization is defined by the requested central package plus the newly created exact task checkout; genuine resume requires existing task-local evidence belonging to that task. The mere presence of inherited integration state is not sufficient to classify a fresh checkout as resume.

Resume-only canonical provenance guards from #15 remain mandatory once task-local managed identity has actually been established.

### Keep task-specific state local or explicitly non-authoritative in integration

Implementation preflight must select the smallest coherent mechanism that prevents a task marker from becoming authoritative identity for unrelated future task checkouts. This may involve state locality, publication cleanup, or explicit origin/classification semantics. Do not introduce a parallel task database unless existing primitives cannot satisfy the contract.

### Provide bounded bootstrap recovery for the already contaminated baseline

The current repository is already in the failure state this change must correct, so implementation needs a one-time bounded path to create the #18 task checkout and materialize its package. Recovery must verify the stale identity, preserve the requested #18 package identity, avoid destructive integration mutation, and remain narrower than a general manual bypass. The recovery mechanics used for this bootstrap are implementation evidence and do not become a second normal delivery path.

### Capture identity before crossing task/integration boundaries

After materialization, carry the executing task's source Issue and change identity across publication, post-merge integration lock, cleanup, and Project-status calls. Do not re-discover source solely from shared integration state after the exact task is already known.

### Treat integration state as a consistency check at terminal boundaries

Integration-visible state may confirm expected identity. If it names another task, that is evidence of contamination and must block managed side effects rather than override task-local identity.

### Preserve remote merge authority

A confirmed exact-head GitHub merge is not rolled back semantically because later local/Project reconciliation cannot resolve identity. Recovery resumes only the remaining side effects for the same task.

### Reuse existing provenance and publication contracts

Do not add fuzzy Issue/PR matching, a second implementation plan, or a second task database by default. Existing canonical OpenSpec provenance, exact-head PR observation, and managed Project reconciliation remain the building blocks.

## Risks / Trade-offs

- Historical integration state may be contaminated and require bounded migration/recovery; correctness is preferred to silently treating stale state as authoritative.
- Changing state locality/cleanup may affect resume behavior, so tests must distinguish task-local resume from integration inheritance explicitly.
- Several lifecycle modules may need signature or state-handling changes; preflight should choose the smallest coherent propagation path and keep quick-task APIs backward compatible.
- The active `adopt-gh-aw-process-automation` change touches completion behavior; this change should land first so later automation inherits the corrected identity boundary.
