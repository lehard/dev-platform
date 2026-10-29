## Context

Reads go through `publication_queue._gh` (`gh api`, with retry for reads). Counted cost today: PR lists, one paginated comment history per candidate, checks, and per-Requirement aggregates. `gh api -i` prints the response headers; with `If-None-Match` a 304 prints the status line and `gh` exits 1.

## Decisions

- **One module, one file.** `github_read_cache.py` owns the cache file `<git-common-dir>/dev-platform/github-read-cache.json` (shared by worktrees and processes on a machine, never committed). Writes are atomic (temp file + rename) under an advisory lock, so parallel overview threads and workers cannot interleave.
- **Whole-body entries, so 304 cannot hide a change.** An entry stores the full response body per request URL (per page) with its ETag. A 304 returns the complete stored body, never a delta; no cursor is kept. The entry is written only after a 200 is fully received and parsed, so an interrupted read leaves the previous entry intact.
- **Conditional GET per page.** `get_pages` / `get_json` sends `If-None-Match` when an entry exists; 200 replaces the entry, 304 reuses it. Paginated listings (PR lists, comment histories) are read page by page by following `Link: rel="next"`, each page conditional; a page set is accepted only if every page is validated or fresh in this call.
- **Only raw responses are stored.** `updated_at` is not used as a validity key: the aggregate of a Requirement depends on machine-local pre-authoring state, so reusing it on an unchanged Issue would be wrong. Its Issue read is conditional instead; assessments, ages and claim expiry are always recomputed. The GraphQL Project-status reads of children have no ETag and stay uncached.
- **Explicit failure, no silent fallback.** Unparsable JSON, unknown schema version, an entry whose stored digest does not match its body, or a structurally invalid entry raises `GithubReadCacheError: GitHub read cache <path> is corrupt (<cause>); delete it to reset: rm <path>`. The reader does not reread instead. A missing file means an empty cache. An entry whose ETag the server no longer accepts is the ordinary 200 path.
- **Equivalence guard.** Results with a warm cache must equal a cache-free read. A test runs the overview twice against a fake GitHub (cold, then warm) and against the same fake with the cache file deleted, asserting identical output and that the warm run charges only conditional requests.
- **Read-only to GitHub stays.** Only GET requests are cached; no write path uses the cache.

## Risks

- `gh` behaviour on 304 (exit 1, headers on stdout) is parsed in one place and covered by a test with recorded transcripts; an unrecognised status raises instead of being treated as 200.
- A comment edit that does not move the PR's `updated_at` is still caught because comment pages are revalidated by ETag on every read, not keyed by `updated_at`.
