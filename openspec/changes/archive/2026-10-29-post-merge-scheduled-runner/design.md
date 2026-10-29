## Context

`work-next --run` claims one job through PR comments (head-bound, TTL, `i_won` re-read), executes it, posts the result, and for post-merge kinds calls `ensure_post_merge_attention`, which marks a spent obligation on the merged PR; the overview already reports it as `post-merge-exhausted`. A claim of a killed run expires after its TTL and becomes reclaimable. A failed run is released by the job itself, counted per job. All of this stays authoritative.

## Decisions

- **A runner around, not inside, `work-next`.** The runner invokes `python3 scripts/lifecycle_workers.py work-next ... --run` as a subprocess in the integration checkout and parses its one-line JSON. No lifecycle module is imported, so claims, trust, attempt limits and attention cannot diverge from what the coordinator runs by hand.
- **Bounded catch-up.** One round runs at most `--max-jobs` work-next runs and at most `--max-seconds`; it stops at `idle` (nothing claimable), at the first failed run (exit != 0 or unparsable output), or when the remainder falls below the threshold. The next round (10 min later) continues: durable state is only GitHub claims/results, so there is nothing to resume locally.
- **Rate limit.** `gh api rate_limit` is not charged. `--min-rest-remaining` is required; below it the round records `skipped` with remaining/reset and exits 0 (a skip is an expected state, not a failure). The remainder is re-read between jobs. A failed rate-limit read is an explicit error.
- **Single instance and crash safety.** A non-blocking `flock` on `<journal-dir>/post-merge-runner.lock`; if held, the round journals `skipped: previous round still running`. A `round-start` without a matching `round-end` found at the start of the next round is journaled as `interrupted-previous-round`. Duplicate claims are impossible by the claim protocol (a new worker identity per work-next run; a live claim of a killed run blocks until its TTL expires); the runner passes a TTL shorter than 2 intervals' work (`--claim-ttl`, default of work-next unchanged unless given).
- **Credentials.** The runner exports `GH_TOKEN` from `gh auth token` into the child only; failure is an explicit error. No LLM, provider or OAuth token is passed: the three kinds are LLM-free.
- **Journal.** `<journal-dir>/post-merge-runs.jsonl`, one JSON object per line, `fsync`-appended; an unwritable journal fails the round. Unreadable journal lines raise on read with the line number. No rotation in this change.
- **launchd.** `launchagent --print` renders the plist; `--install` / `--remove` follow the existing `local_workspace.launchagent` pattern (destination fixed to the user's LaunchAgents, `launchctl bootstrap/bootout`, refuse on unload failure). All paths (python, gh, repo checkout, journal dir) are explicit arguments resolved at render time; none is guessed at run time. Nothing installs automatically.

## Risks

- Counted REST cost per round is roughly one PR/comment read per `work-next` run until the read cache (BR-886) lands; mitigated by `--max-jobs`, the threshold, and journaling the remainder before and after every run.
- A job that fails permanently blocks later PRs for up to the platform attempt limit rounds; after that the platform marks it spent and the next PR proceeds.
