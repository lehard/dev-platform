## Why

PR #837 hung in blocked-retryable with the stale reason "required checks not yet reported on head: validate". Its head conflicted with main only in the generated manifest. The queue had already found that conflict through `merge-tree` in `_prepare` and routed it to the derived merge, but the hosted runner had no OpenSpec CLI (fixed by #840). The resulting `QueueEnvironmentError` leaves the candidate unchanged by design, so nothing on the candidate named the real cause.

## What Changes

- On a coordinator environment failure during integration, the queue posts a v1 `environment-error` note naming the exact head and the failure. The note changes no state, posts no block and spends no attempt. The run still fails with environment-error. The same failure on the same head is not posted again.
- Lifecycle derivation shows that note as the candidate's reason while no later record for that head supersedes it. State, gates and attempts stay as they are.
- Regression tests pin the existing conflict paths. A waiting candidate without a red gate is integrable. A real conflict outside generated files becomes counted integration repair. A conflict only in declared generated files takes the derived merge.
- GitHub mergeability is not read. The queue's own `merge-tree` stays the conflict signal.

## Capabilities

### Modified Capabilities

- `publication-queue`: a coordinator environment failure is visible on the candidate without a block or attempt.

## Impact

`template/scripts/publication_queue.py`, `candidate_lifecycle.py`, tests. Coordinator decision 2026-11-01 narrowing BR-969 item 2 (variant A); D2-B is superseded because the conflict path already exists in code.
