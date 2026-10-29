## Why

The GitHub REST limit (5000/h) is shared by every session, the coordinator and the workers. On 2026-10-28 a board refreshing every 3-4 minutes exhausted it for everyone. A full overview costs about 140 counted requests, almost all re-reading PR comment histories and Requirement aggregates that did not change (BR-886). Conditional requests that return 304 are not charged against the primary limit (confirmed on 2026-10-29: `X-RateLimit-Remaining` unchanged across two `If-None-Match` GETs).

## What Changes

- New `template/scripts/github_read_cache.py`: a local, disposable read cache for GitHub GET responses, revalidated by ETag (conditional request) on every read.
- `publication_queue._comments`, `lifecycle_workers._gh_json` plain GETs (PR lists, comments, PR), `managed_task.fetch_issue` and the Requirement open-issue listing in `lifecycle_overview` read through it; the Requirement Issue read inside the aggregate is revalidated by ETag. Derived values (assessments, aggregates) are never stored.
- Assessments, claim expiry and ages are always recomputed from the (cached or fresh) data and the current time.
- A corrupt or inconsistent cache file raises an explicit error naming the file and how to reset it; an absent file or a merely stale entry is a plain GitHub read.
- Spec: chat-coordinator requirement "read-only projection" is modified narrowly: the overview still writes nothing to GitHub and GitHub stays the only source of truth, but it MAY keep a disposable local read cache. The role line "no second state store" is unchanged.

## Impact

- `template/scripts/github_read_cache.py` (new), `publication_queue.py`, `lifecycle_workers.py`, `lifecycle_overview.py`, tests, `docs/engineering/chat-coordinator.md`, platform manifest.
- Specs: chat-coordinator (modified requirement), lifecycle-workers (added requirement).
