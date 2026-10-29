OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the platform-lifecycle delta against the delivered code (lehard/dev-platform#718, #726), proposal, design and tasks; targeted unit tests; `openspec validate --strict`; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner decision 2026-10-22 (recorded in the Requirement): the BR-748 behind-mergeable rule applies to quick tasks. This change records delivered behavior; no code changes.

## Completeness

- Quick task under the enabled queue behind a cleanly mergeable main passes without reconcile: `tests/test_task_reconciliation.py` `test_queue_integrated_quick_task_behind_a_mergeable_main_finishes_without_reconcile` (finish blockers carry no task-freshness or branch-base; the same head without queue integration does); `tests/test_select_checks.py` `test_without_evidence_a_queue_integrated_task_passes_behind_a_mergeable_main`.
- Same answer as a coordinator-managed candidate across gate, publish step and board: `tests/test_task_base_matrix.py` (`answer` asserts managed == quick for every case: fresh, behind-mergeable with files from main, clean shared file, declared generated file, self-declared generated file, conflict).
- Real conflict still requires reconcile, naming the file: `test_queue_integrated_quick_task_with_a_real_conflict_still_requires_reconcile`; `test_task_base_matrix.py` `test_conflict` (gate and publish name "a trial merge conflicts in conflict.txt").
- Tasks the queue does not integrate keep the fresh-base rule: `test_without_evidence_a_task_the_queue_does_not_integrate_keeps_the_fresh_base_rule`; `tests/test_task_freshness.py` `test_queue_integrates_coordinator_candidates_and_quick_tasks_only_with_the_queue_enabled`.
- The queue admits a genuine quick task under its exact-head identity (accepted publication-queue requirement "Managed admission requires exact task-content provenance", scenario "Genuine quick task"), merges main and gates on the integrated head.

## Correctness

- `_platform_common.queue_integrated` is the one predicate; `require_handoff_task_base`, `finish_task.py`, `project_publish.py` and `task_reconciliation.observe_candidate` read it, and `classify_task_base_currency` is the one classifier, so the delta describes the code as delivered.
- No managed-candidate rule changes: the BR-748 conditions are restated unchanged.

## Coherence

- The scenario "Non-coordinator task keeps the fresh-base rule" keeps its name and now names the tasks the queue does not integrate.
