## 1. Selection
- [ ] 1.1 `lifecycle_workers`: `offer_order`; `select_job` uses it; `work_next` sorts, derives lazily with `resolve_pr`, stops at the first claimable job.
- [ ] 1.2 `candidate_prs`: `lazy` stubs for the label-listing tail; skip settled-labeled closed PRs in the recent page; `merged_at` required for ordering.
- [ ] 1.3 `github_read_cache`: in-process memo keyed by file stat.

## 2. Runner and composition
- [ ] 2.1 `post_merge_runner`: run timeout is the claim TTL; no run starts after the deadline; outcome `max-seconds`.
- [ ] 2.2 `requirement_composition.reconcile_composition` and `integration_contour.run_claimed_post_merge`: composition checkouts with `contract_from=root/.dev-platform.toml`.

## 3. Tests
- [ ] 3.1 Fresh-first order, early stop reads no older PR, idle still settles and raises on skipped, non-post-merge order unchanged, settled skip, lazy stub resolution, read-cache single parse and reload on change, runner timeout and `max-seconds`, composition contract install.

## 4. Verification
- [ ] 4.1 Full validation, measured dry-run selection time, semantic OpenSpec verification.
