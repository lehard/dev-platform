# Verification: claude-execution-evidence-truthful

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of the proposal, design and model-routing delta against the implementation diff and each scenario; check of supported Claude Code surfaces for an existing launch receipt; targeted and full platform tests; live dogfood of the changed `record-claude-execution` on this task's own routing record.

Automated-Checks-Evidence: automated-checks.json

Requirement-Integration-Exception: This Requirement has exactly one technical child, so a multi-child integration candidate cannot be assembled; publish this verified child through its exact managed PR and reconcile the parent after terminal delivery.

## Runtime receipt check

The native Agent tool is invoked by the supervisor's own tool call; its result, including the agent id, reaches only the supervisor's conversation. No platform-owned process observes the launch. Local transcript files are undocumented and are written by the same principal making the claim, so they cannot independently prove a launch. No existing machine-verifiable receipt was found, so no new mechanism was introduced and the id remains a claim.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 -m ruff check template/scripts scripts tests`: passed.
- `python3 scripts/managed_projects.py validate`: passed, three managed projects.
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --all`: passed, all 13 groups. The archive helper reruns the selected checks on the final candidate and records the exact result in `automated-checks.json`.
- `python3 -m pytest tests/test_model_routing.py tests/test_central_dogfood_lifecycle.py tests/test_friction_review.py -q`: 156 passed (executor run, reviewed by the supervisor).
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `openspec validate claude-execution-evidence-truthful --strict --no-interactive`: passed.
- `python3 scripts/check_private_backlog_refs.py` and `git diff --check`: passed.

## Semantic OpenSpec review

- **Arbitrary agent identifier is recorded:** `record_claude_execution` writes `outcome: claimed`, `launch_evidence: self-reported`, `launched: null`, `claimed_agent_id` and a `claimed_participant` whose model source is `self-reported`; it writes no `participant` or `agent_id`. `test_arbitrary_agent_id_is_not_launch_proof` records `anything-made-up` and asserts that shape, that `_launch_confirmed` is false, that the calibration label is `claimed`, and that the gate accepts it only as a clean-postcheck claim.
- **Legacy self-reported launch record reaches the gate:** a Claude record with `launched: true` and `agent_id` but no claimed outcome is refused with a re-record diagnostic (`test_routing_gate_refuses_legacy_self_reported_claude_launch`). A claimed record with a non-clean postcheck is refused (`test_routing_gate_refuses_claimed_claude_execution_with_dirty_postcheck`).
- **Reports:** the efficiency baseline and calibration use `_launch_confirmed`; current and legacy self-reported Claude records are not counted as launched, while a Codex launched record still is (two dedicated tests).
- **Platform-observed Codex launch:** the Codex gate branch keeps the same checks and messages; only the shared `launched` check moved inside it. The existing Codex gate, recovery and abnormal-outcome tests pass unchanged. Retained execution, R1/R2/R3 policy and model selection are untouched.
- **Provenance requirement:** friction executor attribution reads `execution.participant`, which a claim no longer carries, so attribution degrades to no participant rather than an unconfirmed one. Central and template routing docs describe the claimed semantics.
- **Dogfood:** this task was routed R2/standard to a native Claude executor. `dogfood_task.py report-claude-execution` recorded the new claimed shape with a clean postcheck on this task's own routing record, and the terminal gate is expected to accept it only as a claim.

## Residual limits

Terminal completion for a routine/standard Claude route still rests on a supervisor claim plus the verified containment postcheck; the platform cannot prove that the child actually ran, and the record now says so. An active pre-repair Claude routing record must be re-recorded before archive.

## Archive attempt note

The first archive-helper run of the selected checks (`DEV_PLATFORM_TEST_JOBS=3`) failed one timing-bounded test, `test_publication_recovery_cli.BoundedTestDeadlineHelperTests.test_expired_helper_fails_with_process_identity_and_retained_output` (0.3s deadline; the killed helper had retained no partial output). This change does not touch that code; the test passed in the earlier full run and in isolation. The failure classification is `unknown` rather than proven `pre-existing`. The archive was rerun with `DEV_PLATFORM_TEST_JOBS=2`, and all selected checks passed; `automated-checks.json` records that rerun.
