OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the chat-coordinator and lifecycle-workers deltas against `template/scripts/github_read_cache.py` and its call sites, proposal, design and tasks; targeted unit tests (`tests/test_github_read_cache.py`, `tests/test_lifecycle_overview.py`, `tests/test_publication_queue.py`, `tests/test_lifecycle_workers.py`, `tests/test_requirement_intake.py`, `tests/test_parallel_lifecycle_acceptance.py`, `tests/test_shared_writer_guard.py`); a real-GitHub measurement and comparison on lehard/dev-platform; repository-owned selected checks recorded by the lifecycle (full suite)
Automated-Checks-Evidence: automated-checks.json

## Completeness

- Every scenario of the chat-coordinator delta is covered: warm read equals cold and deleted-cache read and spends only conditional requests (`test_warm_read_is_conditional_and_equals_cold_and_deleted_cache`); a change after the previous read is never hidden by a 304 (`test_a_change_after_the_previous_read_is_never_hidden_by_a_304`); a corrupt cache fails naming the file and `rm` reset without a silent re-read (`test_corrupt_cache_fails_naming_the_file_and_reset`, five corruption shapes); an absent or stale cache is an ordinary read.
- lifecycle-workers delta: plain `api` GETs of the worker go through the cache and writes bypass it (`test_worker_reads_fail_the_run_on_a_corrupt_cache_and_never_cache_writes`); the per-PR discovery loop re-raises `GithubReadCacheError` instead of recording a skipped PR.
- Growth past a full last page cannot hide behind a 304 (`test_growth_past_a_full_last_page_is_not_hidden`, fake GitHub whose ETag follows the body only); single-page lists, short pages and objects stay conditional (`test_warm_single_page_lists_and_objects_make_only_conditional_requests`); an undeterminable page size is an explicit error.
- A failed or interrupted read keeps the previous entry (`test_failed_read_keeps_the_previous_entry`).

## Correctness

- Measured on real GitHub (2026-10-29, 51 candidates, 44 Requirements) after the full-last-page repair: main without cache spends 146 counted REST requests per overview; a warm overview spends 2 (`gh repo view` and one `gh auth status`), every list page, comment history and Issue read being a conditional request. The 20 Project-status GraphQL reads of Requirement children are not conditional and remain (separate GraphQL limit). Conditional 304 answers were confirmed not to lower `X-RateLimit-Remaining`.
- The cached overview equals the main (cache-free) overview field for field, except `job_age_minutes` and the finding text embedding it, which differ by the minutes elapsed between runs.
- `updated_at` is not a validity key (deviation from the owner's wording, reported to the owner): the aggregate of a Requirement depends on machine-local pre-authoring state, so it is not stored; only raw responses are, each revalidated by ETag.

## Coherence

- The overview stays read-only to GitHub and GitHub the only source of truth; the role line "no second state store" in the chat-coordinator spec is unchanged. `docs/engineering/chat-coordinator.md` gains a "Read cache" section and the BR-889 `idle:` text is preserved after merging main.
- The new direct writer is recorded in the reviewed shared-writer baseline; the acceptance harness's fake `gh` now serves `api -i` conditional reads; the new script is classified in the protected surface and the platform manifest regenerated.
- The overlap with BR-885 on `dev-platform/checks.toml` (different list entries) was verified safe and acknowledged on the agent board.
