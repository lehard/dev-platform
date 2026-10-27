## Why

Archive's `run_test_groups --all` failed on a timing-bounded test the change did not touch, and the ~8-minute suite had to be rerun (friction lehard/dev-platform#124). The machine often runs at 10–50 load per core. Several platform tests still assert machine speed: a 1-second window for a child's first streamed line, a 1-second poll for a writer to start, a minimum 0.2 s elapsed time measured after a readiness poll, a 2-second grandchild sleep that must outlast a process-group kill, a 5-second self-interrupt poll, and 5-second waits that must not expire. Under load each can fail with no defect.

## What Changes

- Remove the speed assertions or replace them with event-based proofs: the streaming test keeps only the load-monotonic "output arrived long before exit" check; the lock-wait test proves ordering by the holder's release marker observed inside the serialized step; the process-group kill test checks that the recorded grandchild is gone instead of racing its sleep.
- Waits that must not expire use the shared bounded test deadline (`tests/_concurrent_lifecycle.py`, 30 s) instead of 1–5 s.
- The 0.3 s case of #124 already waits for an explicit readiness marker before its deadline starts; unchanged.
- Tests of the BR-768/T2 files are not touched; their timing risks are recorded as remainder.

## Impact

Tests only: `tests/test_git_lifecycle.py`, `tests/test_delegated_write_guard.py`, `tests/test_pr_reconciliation_concurrency.py`, `tests/test_independent_review.py`, `tests/test_deepseek_harness_runtime.py`, `tests/test_requirement_intake.py`. Spec `platform-ci`: one added requirement.
