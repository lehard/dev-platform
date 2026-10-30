## Why

On 2026-10-27 the queue run for lehard/dev-platform#744 ended `no queue candidate could be evaluated: #744 not observable: gh: ... too many files changed (HTTP 422)` with exit 2; the same `pulls/744` read succeeded minutes later and the PR waited about 45 minutes for a manual dispatch. Separately (absorbed #776), a transient failure while integrating moves a candidate to `waiting` with no counter, so a failure that keeps recurring is retried on every run without end.

Note on the Requirement: it says `_pr()` makes one call without retry. `_pr` goes through `_gh` → `run_github_with_retry` (four attempts, 1/2/4 s backoff) for reads, but only for diagnostics matched by the shared transient classification; the 422 text did not match, so there was one attempt.

## What Changes

- Candidate observation in the queue worker reads `pulls/N` through a bounded observation retry: a transient failure (the shared classification, or HTTP 422 "too many files changed", which is treated as transient only for this read) is retried with backoff 15, 30, 60, 120 s; every failed attempt is logged with PR, attempt and error; the last failure is raised naming the PR, the attempts and the error, so the candidate is skipped visibly and a run where no candidate is observable fails with exit 2 as today. A non-transient failure is not retried.
- In `_integrate`, a transient failure increments `attempts["transient-failures:<head>"]` on the candidate record (same state, ownership refused for claims) and returns `waiting` naming the count and limit; at `MAX_TRANSIENT_FAILURES` = 3 consecutive failures on one head the candidate is blocked with reason `transient failure repeated 3 times on head <head>: <error>`. A later non-transient evaluation of the same head writes the counter back to 0; a new head starts its own counter.

## Impact

- `template/scripts/publication_queue.py`, `tests/test_publication_queue.py`, platform manifest.
- Specs: publication-queue (added requirement).
- No change to `_platform_common` classification, merge semantics, admission or repair accounting.
