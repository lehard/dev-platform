## Why

T1 of BR-812 (PR lehard/dev-platform#738) removed speed assertions from six test modules but left `tests/test_lifecycle_workers.py` untouched while BR-768 changed that file. Two of its tests still pass only on a fast host: the group-kill test asserts `run_in_session` returned within 1.4 s and that 1.5 s child sleeps did not finish before the kill; the writer test relies on a background child's 1.5 s sleep outlasting the group kill.

## What Changes

- Background children record their pid as soon as they start and sleep far longer than the test; the leader / fake writer waits for those pids before exiting, so the kill is always exercised on live processes.
- The tests check that each recorded process is gone within the bounded test deadline (`tests/_concurrent_lifecycle.py`). "The pipe holder did not keep it waiting" is proven by `run_in_session` returning within that deadline although the pipe holder would sleep 600 s, not by a 1.4 s bound.
- The late-write markers are still asserted absent.

## Impact

Tests only: `tests/test_lifecycle_workers.py`. Spec `platform-ci`: the T1 requirement "Platform tests do not assert machine speed" is extended with a scenario for process-group kill tests.
