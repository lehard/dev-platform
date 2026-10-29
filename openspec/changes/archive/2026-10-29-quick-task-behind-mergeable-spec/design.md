## Context

Delivered code: `_platform_common.queue_integrated` (coordinator lifecycle mode, queue enabled on authoritative main, and either no canonical managed provenance or a coordinator candidate), used by `require_handoff_task_base`, `finish_task.py`, `project_publish.py` and `task_reconciliation.observe_candidate`; one classifier (`classify_task_base_currency`).

## Decisions

- Owner decision 2026-10-22, recorded in the Requirement: the BR-748 rule applies to quick tasks. No new decision is made here.
- The delta restates the existing requirement with the widened exception rather than adding a parallel requirement, so one requirement owns the fresh-base rule and its exceptions.

## Verification

Acceptance is checked against the existing tests first: same gate answer for a managed and a quick task, a quick task's own run needing no reconcile, `queue_integrated` only with the queue enabled, and a real conflict blocking. A missing case gets one test.
