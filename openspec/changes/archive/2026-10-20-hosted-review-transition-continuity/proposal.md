## Why

On 2026-10-19 hosted review of lehard/dev-platform#619 ran six rounds. Two rounds found material findings but could not record `repair-pending`: coordinator friction resolves the candidate's Requirement through `managed_task.authoring_config`, and the hosted runner installs the public `dev-platform/source-contract.toml`, which has no `[development_backlog]`. The transition failed after the review evidence had been pushed. Three other rounds discarded their own result right after their own lease push (the PR API still reported the previous head). Every orphaned push was then recovered as "validated worker push; repeat review" with `gates={}`, so the admission gates (`semantic-verification`, `selected-checks`, `developer-friction`) were lost although the task-content digest never changed. The candidate reached `finalize-pending` only by rerunning review, and finalization now refuses it with "fresh semantic verification required"; the developer has no supported re-handoff path (lehard/dev-platform#624).

## What Changes

- Coordinator friction is attributed to the Requirement through its public work identity (`BR-N`, child `BR-N/TM`), derived from the managed candidate branch by a pure function. The friction sink no longer reads the authoring configuration or the Backlog, so it works on the hosted runner, and no private Backlog reference is written to the public pull request. The Requirement retrospective matches durable records by that identity.
- A review or repair job derives the attribution for its candidate after claim validation and before the reviewer starts, so an unattributable candidate fails before any evidence push, naming the cause.
- After a successful lease push a worker waits a bounded time for the PR head to converge to the pushed head. A foreign head or a changed claim still discards the job; non-convergence is an explicit failure, not a silent discard.
- Gates bound to task-content identity survive a head reached by a trusted harness push when the content digest is unchanged, including the validated-push recovery and the next claim transition.
- A coordinator command `publication_queue.py restore-gates --pr N` restores content-bound gates lost before this change, only after proving a chain of trusted harness pushes with an unchanged content digest from the gated record to the current head; otherwise it refuses with the reason and next step.

## Impact

- `template/scripts/publication_queue.py`, `candidate_lifecycle.py`, `pr_review_gate.py`, `lifecycle_workers.py`, `integration_contour.py`, `post_review_finalization.py`, `managed_work_identity.py`.
- Docs: `docs/engineering/hosted-lifecycle-workers.md`, `docs/engineering/chat-coordinator.md`, `docs/engineering/agent-workflow.md` (finalize-pending with lost gates).
- No private Backlog identity enters a public commit or pull request record; no new state, credential or workflow secret. Spec: `lifecycle-workers` (added) and `publication-queue` (modified durable evidence binding).
