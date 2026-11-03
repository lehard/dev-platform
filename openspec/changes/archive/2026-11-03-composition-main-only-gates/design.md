## Existing behavior and remaining scope

BR-969 already supplies `task_content_identity.main_only_integration`, `integration_contour.main_only_reason` and post-repair reusable-gate carry in `advance_after_repair`. Reuse those implementations. Keep `equivalent_proofs` and existing child/quick-task behavior.

## Decisions

- **Proof-bound full-check evidence.** Clean composition refresh uses the existing main-only proof against the trusted queue head whose gates passed. Carry the original check evidence together with its old head, new base and new head. `require_final_gates` accepts the old evidence head only when the proof and trusted passed gates establish validity for the new head; do not rewrite it as a fabricated check run.
- **Required CI before ready.** Required-check evidence does not carry. A proven update waits for passed required CI on its exact head before ready or admission; pending, failed, unavailable or stale-head CI cannot satisfy this gate.
- **One final-publication pass after genuine repair.** For compositions, connect the existing repair completion to `advance_final_publication` once. Unchanged own content receives one full-check pass and admission. Changed own content uses the existing full-review return path, then finalization and final publication; it never receives a conflict-only review.
- **Preserve main-only carry.** A repair result that proves to be only main integration retains the accepted BR-969 reuse behavior rather than entering the genuine-repair full-check path.
- **Preserve queue boundaries.** Environment failure without a merge-tree conflict records the head/reason without state change or attempt consumption. Real conflicts, including generated-only conflicts when derived merge is unavailable, keep the existing integration-repair policy.

## Risks and verification

An incorrect trust anchor could reuse checks for unreviewed content: obtain the old head only from the trusted gated queue transition and retain default-branch generated-file declarations. Missing or invalid evidence prohibits reuse with an explicit reason; Git/proof execution errors stop explicitly. Verify clean refresh, rejected proof, stale evidence, pending/failed/stale-head CI, genuine repair, changed-content review and unchanged child receipts. Do not broaden this child into a proof-helper rewrite or queue policy change.

## Event-driven final publication continuation

After finalization or genuine integration repair, the existing lifecycle worker runs the necessary full-check pass once and records its passed gate and a pending exact-head required-CI gate on the composition candidate in `blocked-retryable`; it does not mark the PR ready or admit it. If CI is already passed on that exact head it continues immediately. The publication-queue workflow already runs on completion of Platform CI; on each event its existing worker discovers the bounded inventory of `blocked-retryable` composition candidates, re-reads their trusted candidate record and observes the required CI for the recorded head. A passed observation resumes publication using the recorded full-check evidence without rerunning full checks. Pending remains explicitly waiting; failed, unavailable, invalid or stale-head evidence is explicitly blocked with a named reason. The worker must not treat unrelated blocked candidates as this wait and must preserve admission ordering. The persisted gate and exact-head checks make repeat events idempotent. The workflow and worker remain existing actors; no polling, new daemon or machine configuration is introduced.

For a queue-owned clean main refresh, the trusted queue update supplies the replaced gated head and base to the existing main-only proof. A proof binding preserves the original full-check evidence and old head, and required CI is observed independently for the new head. If CI has not passed, the candidate waits without a new ready record; a subsequent CI event retries the same trusted update. Failed proof or missing gate evidence blocks explicitly and does not run a substitute check. Genuine repair of unchanged own content instead executes one full-check pass; changed own content returns to full composition review and existing finalization.

If the integration-repair worker is interrupted after its push before publication evidence is recorded, recovery must not infer readiness: it records an explicit block naming the missing full-check and exact-head CI proof.
