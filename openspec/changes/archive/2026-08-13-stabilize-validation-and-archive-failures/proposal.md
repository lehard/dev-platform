# Proposal: Stabilize validation and OpenSpec archive failures

## Why

Concurrent validation still exposes a shared-workspace fixture failure that disappears in isolation, while lifecycle failure reporting collapses distinct validation causes into one generic signal. Separately, OpenSpec archive runs expensive checks before deterministic readiness preflights and can write stale evidence for an invocation that should have failed immediately.

These are one feedback-loop reliability cluster: prove readiness cheaply, run stable relevant checks, and preserve an actionable failure signal.

## What Changes

- Make the affected managed-task/shared-workspace validation path deterministic under supported concurrency or serialize only the proven unsafe group.
- Preserve bounded structured check/group failure context in lifecycle friction.
- Move OpenSpec archive static/state preflight before expensive checks and before evidence mutation.
- Keep real failures observable without blind retries.

## Impact

- Modified specifications: `platform-ci`, `completion-lifecycle`.
- Expected surfaces: test-group fixtures/concurrency, `select_checks`/`finish_task` failure reporting, `openspec_lifecycle.py`, evidence receipts and focused tests.
