## Context

`worker()` reads each queued PR with `_pr` before evaluating; a `QueueError` skips the candidate (`not observable`) and the run raises when every candidate failed. `_integrate` maps a `TransientQueueError`, a transient `CalledProcessError` and a transient `GitCommandError` to `waiting` (BR-767) without counting. `_transition(..., set_attempts=...)` publishes a record with updated attempt counters (de-duplicated when nothing changes); attempt counters carry forward across coordinator head updates.

## Decisions

- **Observation retry local to the queue (coordinator decision 2026-10-27, variant A).** `_observe_pr(root, repo, number, *, sleep=time.sleep)` wraps `_pr`. `OBSERVATION_BACKOFF = (15, 30, 60, 120)` gives at most five reads within about four minutes of a twenty-minute job. Retried: `TransientQueueError` and a `QueueError` whose text matches `too many files changed` with `HTTP 422`. Each failed attempt prints `publication queue: #N observation attempt k/5 failed: <error>` to stderr. Exhaustion raises `TransientQueueError("#N not observable after 5 attempts: <error>")`. Rejected: a self-dispatching workflow retry (needs `actions: write`), widening the shared classification (other callers would retry a 422 on writes).
- **Head-scoped counter.** The key `transient-failures:<head>` resets on a new head without a delete operation (carried-forward keys of older heads are inert). `_count_transient(root, repo, number, head, detail)` derives the candidate, reads the exact-head record's counter, and either publishes `n+1` through `_transition` with the derived state and `refuse_from=CLAIM_STATES` (a claim that took the candidate meanwhile wins and the result is plain `waiting`) or, at the limit, `_block`s with the reason. `_integrate`'s two transient branches call it.
- **Reset.** After `_integrate` returns an outcome that keeps integration ownership (not released, not `merged`) without a transient failure, the worker resets a non-zero counter for that head to 0 through the same `_transition`. Released outcomes (ownership taken by other lifecycle work, finalization pending) and blocks do not reset. The extra reads happen only for the evaluated candidate.
- **No fallback.** A failure to publish the counter or the block raises as today; the counter never substitutes a default for an unreadable record.

## Risks

- The longer backoff lengthens a run whose PR is unobservable by up to about four minutes; the job timeout is twenty minutes.
- Counter records add at most one comment per transient run per candidate, bounded by the limit.
