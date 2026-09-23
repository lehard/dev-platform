# Design: Board projection of canonical Requirement progress

## Inputs and precedence

Read the Requirement Issue and primary Project item through the existing read-through progress adapter. Blocked, stale, missing and contradictory states outrank optimistic stages. A ready child receipt means integration-ready, not delivered. Exact merged PR evidence is owned by shared publication, not inferred from child status.

## Projection

Map started pre-authoring, ready-to-materialize and execution to the Project's In progress status, and consequential decision or source failure to Blocked. The richer read-through stage remains available in the projection response. The terminal transition is made only inside the existing exact-merged-PR reconciliation boundary, after main synchronization, parent-link verification and child Done reconciliation. Nonterminal reconciliation compares the computed state with the existing parent card and changes only that item when evidence warrants it. The output retains a reason/source trace for diagnostics.

## Recovery

Repeated reconciliation is idempotent. A stale or ambiguous publication candidate cannot produce Done. Drift is reported and repaired only when the source state is authoritative; a read failure never writes an optimistic status. A post-merge Project API failure leaves the publication operation incomplete and is recoverable by retrying the exact candidate publication; it never reports the Requirement complete.
