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
