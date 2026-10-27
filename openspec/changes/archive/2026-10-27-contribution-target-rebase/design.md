## Context

- `post_review_finalization` publishes `contribution-integration` with `target_head=adapter.branch_head(root, target_branch)`.
- `lifecycle_workers` runs the claimed job through `merge_reviewed_contribution(..., expected_target_head=job["target_head"])` and posts the returned state as the job result.
- `merge_reviewed_contribution` returns `discarded` when `HEAD` of the fresh target checkout differs from `expected_target_head`, and again when `ls-remote` shows the branch moved before the protected merge.
- `job_id` includes `:t<target_head>`, so a job re-published with another `target_head` is a new job, not a retry of the stale one.

## Decisions

- **Re-offer, do not merge on an unproven head.** The worker never merges onto a head the job was not bound to; it re-publishes the same job kind for the same candidate head and identity, bound to the observed moved head, and returns `target-moved`. The next worker claim performs the normal checks (dependencies, conflicts, protected merge) on that head.
- **Base containment is required.** The moved head must contain `contribution_base` (`merge-base --is-ancestor`, fetching the moved head first when it was observed through `ls-remote`). Otherwise the requirement branch was rewritten under the contribution; that raises `ContributionError` naming the base and the moved head, which the worker reports as a failed job, never a silent discard.
- **Claim first.** Re-offer happens only while the claim is current; a lost claim returns `discarded` without publishing.
- **Attempt unchanged.** `publish_job` keeps the candidate's current `contribution-integration` attempt; the job id differs by `target_head`. Repeated moves re-offer once per observed move.
- **Scope.** `publication_queue.py`, `lifecycle_workers.py` and finalization are not changed.

## Risks

- A requirement branch that moves on every run re-offers each time; it is bounded by the number of contributions integrating.
