## 1. Derivation and worker
- [x] 1.1 `candidate_lifecycle.post_merge_release_limit`, `released_reason`; `derive_candidate` and `post_merge_job` treat a released-out post-merge job as exhausted.
- [x] 1.2 `lifecycle_workers.main`: post-merge kind reaching `MAX_RELEASES` posts `ensure_post_merge_attention`; pre-merge escalation unchanged.
- [x] 1.3 `pr_review_gate.permitted_post_merge_actions`: last-outcome text from the release detail.

## 2. Tests
- [x] 2.1 Offered below the limit, exhausted with count and cause at the limit; attention and permitted action name releases and the re-offer command; re-offer restores a job; third release posts the attention and no `blocked-escalation`.

## 3. Verification
- [x] 3.1 Full validation and semantic OpenSpec verification.
