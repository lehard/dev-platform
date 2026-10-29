## 1. Read cache
- [ ] 1.1 Add `github_read_cache.py`: cache file, atomic locked writes, digest-validated entries, explicit `GithubReadCacheError`, `get_pages` / `get_json` (per-page, 304 parsing).
- [ ] 1.2 Route `publication_queue._comments`, the PR list in `lifecycle_workers.candidate_prs`, `_open_requirements` `managed_task.fetch_issue` (used by the aggregate) and `lifecycle_workers._gh_json` plain GETs through it; writes bypass.
- [ ] 1.3 Update the `lifecycle_overview.py` module docstring, `docs/engineering/chat-coordinator.md` and the platform manifest; classify the new script.

## 2. Verification
- [ ] 2.1 Tests: 304 reuse, 200 replace, comment/PR change visible after warm read, interrupted read keeps old entry, corrupt file / bad version / digest mismatch raise with path and reset, absent file is a cold read, cold == warm == deleted-cache overview, writes not cached.
- [ ] 2.2 Measure counted requests for a repeated real `lifecycle_overview.py` and compare cache vs full `--json` output on real data; attach both to the receipt.
- [ ] 2.3 Run full validation and semantic OpenSpec verification.
