# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/spec delta against the diff, plus targeted unit suites and the selected-check run recorded in automated-checks.json
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Ordinary lifecycle commands do not retry friction routing: `agent_doctor.retry_friction_routing` and its call (doctor, and `start`, which runs doctor) and `finish_task.run_friction_route_pending_retry` and its call (finish/advance preflight) are removed; neither module references `route-pending` any more. Retained events stay pending in the local state; `agent_friction.py route-pending` remains the explicit retry and now reports `routed`, `failures` and `withheld`. Doctor's local friction review status line is unchanged.
- Coordinator events carry reason and candidate: `publication_queue.friction_reason` builds a bounded reason from the transition's red gate (`name: cause; limitation`, else `name: evidence`); a transition without a named red gate, or a red gate with no cause or evidence, raises `QueueError` naming the PR and state. The durable evidence record requires `reason`; old records without it still read and are withheld at routing; a present-but-empty reason is an invalid record. `integration_contour.default_friction_sink` mirrors `reason` and `candidate {task, number, head}` into `append_coordinator_event`, which validates both. `finish_task.record_lifecycle_friction` passes `--reason` (from the selector failure descriptor for `lifecycle-validation-failure`, the exit status for OpenSpec hygiene) and `--candidate-task/--candidate-head`; `record` rejects coordinator categories without them and validates the head SHA.
- Router: `route_body` renders `- Candidate:` (branch, PR, 12-char head) and a `### Reason` section through `sanitize_for_route`; evidence stays local. `route_event` records a coordinator-category or coordinator-attributed event lacking reason or candidate as `withheld` with the missing field named, posts nothing, and `route_pending` skips `withheld` routes on later runs.
- Spec delta scenarios map to tests: doctor/finish no routing (`test_doctor_and_finish_never_wait_on_friction_routing`), explicit retry counts (`test_unavailable_routing_stays_pending_then_retries`, `test_faceless_coordinator_events_are_withheld_and_not_retried`), routed cause (`test_routed_body_names_reason_and_candidate`, `test_reason_names_the_red_gate_cause`), validation failure reason/candidate (`test_validation_failure_reason_names_failure_class_and_checks`, `test_finish_records_validation_failure_with_reason_and_candidate`), producer without reason (`test_transition_without_a_red_gate_reason_fails_explicitly`).
- Overlap with lehard/dev-platform PR 619 (open at implementation time): no shared hunks in `agent_friction.py` (it edits `read_events`, `read_state`, `destination_for`, `process_label`, `platform_repository`, checkpoint), `dev-platform/checks.toml` (different group) or `tests/test_friction_review.py` (different lines).

## Checks actually run

- Targeted: `tests/test_coordinator_event_routing.py` (new), `tests/test_coordinator_evidence.py`, `tests/test_harness_safety.py`, `tests/test_friction_review.py`, `tests/test_autonomous_integration_contour.py`, `tests/test_finish_merged_queue.py`, `tests/test_pr_review_gate.py`, `tests/test_candidate_lifecycle.py`, `tests/test_publication_queue.py` pass.
- `docs/engineering/agent-workflow.md`: the new routing paragraph sits after the disposition paragraph so it does not touch the line BR-696/T1 edits (merge-tree with that branch is clean). `compileall`, `managed_projects.py validate`, `openspec_lifecycle.py check`, `run_test_groups.py --verify-coverage`, `generate_platform_manifest.py --write` run clean. Authoritative selected-check evidence for the committed candidate: `automated-checks.json`.

## Limitations

- Not exercised against live GitHub routing or a live coordinator run; routing and coordinator paths are verified with the existing fakes.
- Existing faceless comments on lehard/dev-platform#176 are untouched by design (Requirement exclusion).

## Re-verification after integration with main (2026-10-20)

- Candidate head `7d71c612` (archive, coordinator integration of main, review evidence) reconciled with main `e4f7b0fd`, which brought lehard/dev-platform PR 619 (strict friction routing/log), PR 647 and PR 657. Conflicts: the `platform-lifecycle` main spec (both changes append requirements; both kept, PR 619's first) and the generated platform manifest (regenerated). `agent_friction.py` merged without conflict; the strict log reader and translated route keys of PR 619 leave the `withheld` route status and the reason/candidate fields intact (`test_friction_strict_log`, `test_retrospective_attribution`, `test_coordinator_event_routing` pass together).
- Semantic finding fixed on this head: production paths (`post_review_finalization` for a requirement composition, `requirement_composition` after the Requirement retrospective) record `blocked-retryable` without a red gate while waiting on exact-head required checks, the state PR 657's `red_retry_blocks_integration` lets integrate. The previous head would have failed those transitions with `QueueError`. `emit_friction` now records no friction event for a red-gate-less `blocked-retryable`; every other friction state still fails explicitly without a named red gate. Spec requirement text, a new scenario ("Waiting on required checks is not friction"), design decision 3, docs and `test_waiting_on_required_checks_records_no_friction` were updated accordingly; `test_hosted_review_continuity` (from PR 657) passes.
- A combined ad-hoc pytest run showed `test_post_review_finalization::test_admission_requires_finalization` failing once; it passes in isolation and is unrelated to friction; the grouped selected-check run below is authoritative.
- Selected checks rerun on the reconciled head; authoritative evidence: `automated-checks.json` in this archive directory.

## Re-verification after second reconcile (main a7a11efe)

- Main brought BR-695/T1 (root-cause convergence and auto-close in `agent_friction.py`, PR 656) and the retained-outcome fix (PR 662). Conflicts only in the `platform-lifecycle` main spec (both append requirements; both kept) and the generated manifest (regenerated). In the auto-merged `route_event`, the withheld check for faceless coordinator events still runs before the root-convergence lookup and issue creation, and `route_pending` still skips `withheld`; `test_friction_root_convergence`, `test_coordinator_event_routing`, `test_coordinator_evidence`, `test_friction_strict_log` and related suites pass together (165 tests). The semantic review above holds unchanged for this change's own content.
- Selected checks rerun on this head; authoritative evidence: `automated-checks.json`.

## Re-verification after third reconcile (main 5978f471)

- Main brought PR 664 (re-admission of a reconcile-pushed descendant head in `publication_queue.local_status` and finish). It touches the queue's local status path only, not `emit_friction`/`friction_reason`; the only conflict was the generated manifest (regenerated). Coordinator evidence, routing and queue suites pass on the merged tree. Semantic review unchanged; selected checks rerun on this head (`automated-checks.json`).

## Semantic verification for developer re-admission (main 4fbf8445, against proven head 7d71c612)

Content changed since the coordinator's proven head `7d71c612`, re-checked against the spec delta and design:

- Merges of main up to `4fbf8445` (PR 619 strict friction log, PR 647/657/664/670 queue re-admission, PR 656 root convergence, PR 662 retained outcome, BR-723). Conflicts were limited to appended requirements in the `platform-lifecycle` main spec (all kept) and the generated manifest (regenerated by `generate_platform_manifest.py`). PR 670 adds `semantic_readmission` in `publication_queue.py` and does not touch `emit_friction`/`friction_reason`.
- In-task fix (behavioral, within this change's scope): a `blocked-retryable` transition without a red gate (waiting on exact-head required checks) records no friction event instead of failing; every other friction state still requires a named red gate. Covered by the spec scenario "Waiting on required checks is not friction" and `test_waiting_on_required_checks_records_no_friction`.
- Routing record: owner-approved supervisor-retained execution recorded with `record-retained-execution`; `verify-routing` reports outcome `retained`, policy `owner-approved`.
- Developer-side independent review on head `60670616`: spec-fidelity 0 findings; engineering-quality 4 advisory findings, kept as designed: no automatic `route-pending` caller (the Requirement makes retry explicit), replay of a friction state without a red gate fails explicitly (design decision 3), the published reason may carry up to 240 characters of red-gate evidence (the same evidence is already published in the durable coordinator record on the PR), and the no-retry test asserts on module source text.
- Spec delta, proposal and design still describe the implemented behavior; tasks are complete. Focused suites (coordinator routing/evidence, publication queue, finish merged queue, hosted review continuity) pass on the merged tree; authoritative selected-check evidence: `automated-checks.json` in this directory.
- Known flaky test recurrence during this task: `test_lifecycle_workers` process-group kill (lehard/dev-platform#530), group `fast-c`; it passes in isolation and the full group passes alone; recorded as friction.
