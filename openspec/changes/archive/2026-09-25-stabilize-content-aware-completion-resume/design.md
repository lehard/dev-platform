# Design: Content identity plus terminal publication resume

## Decisions

1. **Evidence represents validated task content.** Exact commit SHA remains recorded provenance, but freshness is decided by a deterministic task-content identity or an equivalence proof, not by `current HEAD == recorded HEAD` alone.
2. **Reuse requires proof.** A checkpoint/check result may survive an expected lifecycle-only transition only when the platform proves task-owned content is unchanged. Ambiguous base changes or relevant upstream overlap fall back to revalidation.
3. **No time-only cache.** Recency by wall clock never substitutes for content identity.
4. **Remote publication has phases.** Once the exact task head has an existing PR and durable auto-merge intent, subsequent completion calls first reconcile observed remote state. They do not repeat first-publication validation/push/create unless the prior intent is missing or materially changed.
5. **Nonterminal is not a crash.** Pending checks, auto-merge armed but not yet merged, and bounded local wait exhaustion are structured resumable outcomes with next action/status. Raw `CalledProcessError` is reserved neither as user contract nor as state classification.
6. **Required checks stay authoritative.** Cheap resume does not bypass GitHub required checks, merge queue or exact-head safety.
7. **Mutation invalidates evidence.** Any change to task-owned content after evidence creation forces the relevant retrospective/validation path again.

## Candidate content identity

Prefer an existing or minimally extended artifact derived from the task's semantic diff/content against its managed base. The implementation may use a deterministic diff/tree digest or equivalent proof, provided it distinguishes task-owned content mutation from merge/archive bookkeeping and remains auditable in receipts.

## Reconcile rules

- Lifecycle-only/archive commit with identical task content: evidence MAY remain fresh.
- Clean upstream advancement proven irrelevant to task content: evidence MAY be reused subject to current verification policy.
- Upstream overlap, conflict, changed task diff or ambiguous equivalence: evidence is stale; rerun selected checks.
- Existing exact-head PR with auto-merge armed: observe/status first.
- Remote intent/head/check state changed materially: route to explicit reconcile/revalidation rather than assuming success.

## Verification

Exercise archive-only HEAD movement, clean unrelated reconciliation, actual task-content mutation, armed auto-merge bounded wait, repeated finish and eventual remote merge/local sync.
