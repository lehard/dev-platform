## 1. Observation retry
- [x] 1.1 `_observe_pr` with `OBSERVATION_BACKOFF`, 422 "too many files changed" classification local to the read, per-attempt log, explicit exhaustion error; used by `worker()`.

## 2. Transient counter
- [x] 2.1 `_count_transient`: head-scoped counter in the record, `waiting` with count, block at `MAX_TRANSIENT_FAILURES`.
- [x] 2.2 Reset a non-zero counter after a non-transient evaluation; new head starts at 0.

## 3. Tests and verification
- [x] 3.1 Tests: transient 422 then success evaluates the candidate; persistent 422 fails naming the PR after the bound; non-transient not retried; no real sleeps; N transient runs give `waiting` with counter then block; reset by a successful evaluation and by a new head.
- [x] 3.2 Regenerate the manifest; full validation and semantic OpenSpec verification.
