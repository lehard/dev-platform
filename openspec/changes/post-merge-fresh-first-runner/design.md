## Context

`lifecycle_workers.work_next` lists candidates (`candidate_prs`: open PRs, one page of 50 recently updated closed PRs, and every closed `lifecycle:merged` PR not labeled `post-merge:settled` read through `pulls/N`), reads every candidate's comments, derives every candidate, and `select_job` returns the first claimable job in ascending PR number. Every `_gh_json` read goes through `github_read_cache`, whose `_load` parses the whole JSON file each time. `post_merge_runner` passes `timeout=min(claim_ttl, remaining budget)`.

## Decisions

- **Offer order.** One key function `offer_order(pr)`: when the requested kinds are all post-merge kinds, open PRs sort first (ascending number), then merged PRs by `merged_at` descending (number descending as tie-break); otherwise ascending number as today. `select_job` sorts with the same key so a direct call keeps the contract.
- **Lazy derivation.** `candidate_prs(..., lazy=True)` returns label-listing tail PRs as stubs `{"number", "merged_at", "labels", "state": "closed", "merged": True, "unread": True}` built from the Issues listing (`pull_request.merged_at`); `work_next` takes `resolve_pr` and reads `pulls/N` for a stub only when it is reached. `work_next` sorts by `offer_order`, then for each PR reads comments, derives, labels a settled chain, and calls `select_job` on that single candidate; the first job ends the scan. Without a job it continues, so an idle run still derives everything and raises on `skipped` exactly as before. The overview keeps `lazy=False` (eager, unchanged output).
- **Settled skip.** `candidate_prs` drops a closed recent-page PR carrying `post-merge:settled`: the label is written only when derivation shows no next job and no exhausted obligation, and a re-offer applies only to an exhausted (never labeled) obligation.
- **Read cache reuse.** `_load` keeps `(path, st_mtime_ns, st_size) -> parsed content` in a module-level memo under the existing lock; any stat change reloads and validates. `_store` updates the memo with what it wrote and the new stat. Corruption still raises `GithubReadCacheError`; every read still revalidates with GitHub (ETag).
- **Round budget as start window.** The loop already stops at `monotonic() >= deadline` before a run; the run's timeout becomes `claim_ttl`, so the round budget never kills a run. A run killed at the claim TTL still fails the round. The single-instance lock already turns an overlapping start into `round-skipped`.
- **Trusted contract for composition checkouts.** `reconcile_composition` and `integration_contour.run_claimed_post_merge` (composition branch) call `prepare_checkout(..., contract_from=root / ".dev-platform.toml")`, as composition child checkouts already do with their trusted checkout. A missing file fails in `install_source_contract`; no key is defaulted.

## Spec delta shape

New requirements are added rather than modifying the existing runner and discovery requirements, whose bodies exceed the 500-character limit of newer OpenSpec and are being split by a separate change; the added ones narrow behavior without contradicting them (the runner's "maximum duration" bound becomes explicitly a start window; a settled PR in the recent page has no obligation to consider).

## Risks

- Ordering by `merged_at` relies on the field in the closed listing, `pulls/N` and the Issues `pull_request.merged_at`; a missing value fails the run naming the PR rather than guessing an order.
- An older settled-but-unlabeled PR is labeled only when a run reaches it; idle runs reach all.
- The cache memo is per process; another process's write changes mtime/size and forces a reload.
