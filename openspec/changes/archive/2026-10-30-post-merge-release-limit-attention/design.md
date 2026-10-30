## Context

`lifecycle_workers.release_claim` posts a `released: <cause>` result; `job_completed`, `job_outcomes` and the post-merge attempt counting ignore released results, and `is_claimable` refuses a job released `MAX_RELEASES` times. `candidate_lifecycle.post_merge_progress` derives the next post-merge job and the exhausted kind from trusted outcomes; `derive_candidate` turns exhaustion into `reason` and `post_merge_exhausted`, which drive `publication_queue.ensure_post_merge_attention`, the overview's `post-merge-exhausted` finding and `pr_review_gate.post_merge_reoffer_plan`.

## Decisions

- **Release exhaustion is post-merge exhaustion in derivation.** `post_merge_release_limit(candidate, job, comments, trust)` counts trusted released results of the exact offered job id (kind, head, attempt, re-offer sequence) with `lifecycle_workers._releases`; at `MAX_RELEASES` `derive_candidate` (and `post_merge_job`) offers no job and records the kind as exhausted with a release-specific reason and `post_merge_released = {kind, attempt, releases, last}`. The reason keeps the `post-merge … exhausted` shape the attention and overview already match. Rejected: a separate attention path or state (duplicates BR-925's re-offer and the overview finding).
- **Attention from the worker.** In `work-next`'s failure branch, a post-merge kind reaching the limit calls `publication_queue.ensure_post_merge_attention` (idempotent per exact state); a failed post raises `WorkerError` naming both the attention failure and the run failure. Pre-merge kinds keep `blocked-escalation`.
- **Re-offer.** A re-offer changes the job id suffix (`:r{seq}`), so released results of the old id no longer count: fresh release budget without a new rule.
- **Permitted action text.** `permitted_post_merge_actions` names `claim released N times: <cause>` instead of an unknown last outcome when `post_merge_released` is present.

## Risks

- Released results are trusted only from coordinator-trusted authors, as today; untrusted ones neither exhaust nor block.
