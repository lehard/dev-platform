# Proposal: Stabilize dogfood and validation failure signals

## Why

Parallel test execution exposed contention-sensitive short deadlines that create false failures, while dogfood completion can produce a second false failure after successful delivery when cleanup invalidates the caller's current directory.

Both are bounded reliability defects in the platform feedback loop. Batching them deliberately pays one lifecycle/validation cycle without changing their independent semantics or broadening into general test/lifecycle redesign.

## What Changes

- Replace fragile timing assumptions in the confirmed concurrent-test fixtures/paths with explicit readiness and reasonable bounded deadlines.
- Keep real hangs/failures observable; do not introduce blind retries.
- Make terminal dogfood completion truthful when invoked from the worktree being cleaned, accounting for the parent caller's cwd rather than only the child Python process.
- Defer cleanup through an existing/small bounded recovery path when synchronous deletion would invalidate the caller; never downgrade real publication failure.

## Impact

- Modified specifications: `platform-ci`, `central-dogfood-lifecycle`.
- Expected surfaces: targeted concurrency test fixtures/runtime timeout probes, `finish_task.py`/dogfood cleanup behavior, cleanup recovery tests and focused docs if behavior changes.
