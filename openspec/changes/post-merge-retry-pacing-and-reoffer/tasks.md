## 1. Runner pacing and environment
- [x] 1.1 `lifecycle_workers.work_next`/`select_job`: `exclude_prs`; `work-next --exclude-pr` (repeatable).
- [x] 1.2 `post_merge_runner`: per-round exclusion of PRs whose run ended `blocked`/`failed`; journal the exclusion; `lsof` PATH check before the first claim.
- [x] 1.3 `integration_contour`: `PostMergeEnvironmentError` for `process-check-unavailable`, re-raised by `run_claimed_post_merge` without a receipt.

## 2. Re-offer
- [x] 2.1 `candidate_lifecycle.post_merge_job`: re-offer sequence, completion across sequences, fresh budget under the current sequence.
- [x] 2.2 `lifecycle_workers.job_record`: re-offer for post-merge kinds.
- [x] 2.3 `pr_review_gate.post_merge_reoffer_plan` and `reoffer_post_merge`; `publication_queue.py reoffer-post-merge` CLI.
- [x] 2.4 `lifecycle_overview` and `publication_queue.attention_body`: list the exact command from the shared eligibility.

## 3. Tests and docs
- [x] 3.1 Tests: pacing and other PRs served, environment failure posts no receipt and fails the round, lsof precheck, re-offer refusals (not merged, head mismatch, not exhausted, live claim) and success, fresh budget and completed kinds not re-run, overview/attention command, `already-clean` completion.
- [x] 3.2 `docs/engineering/chat-coordinator.md`: the new operator command; regenerate the platform manifest.

## 4. Verification
- [x] 4.1 Full validation and semantic OpenSpec verification.
