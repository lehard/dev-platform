OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-lifecycle delta, proposal, design and tasks; targeted unit tests (test_rollout_preflight incl. PlatformLagTests, test_managed_task start-path tests, test_managed_intake_project_harness_isolation) passing; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (deterministic depth, no ADD). The Requirement delegates warn-vs-stop to design: warn and continue, recorded in the spec requirement, because updates are a deliberate owner action since automatic rollout was disabled.
- Undeterminable inputs raise `PlatformLagError`; `start_task` stops before creating anything. No skip.
- Latest = the platform source's latest GitHub release (`releases/latest`), required to be a stable `vX.Y.Z`.

## Completeness

- Behind: both versions and `gh workflow run rollout.yml --repo <source> -f version=<latest> -f repository=<project>` in the report: `test_lagging_project_gets_both_versions_and_the_exact_update_command`; start prints it and still creates the task branch, measured on the re-read config: `test_lagging_project_reports_the_update_command_and_still_creates_the_task_branch`.
- Current (equal or newer) prints nothing: `test_project_on_or_past_the_latest_release_is_current`.
- Platform source checkout not applicable without any GitHub read: `test_platform_source_repository_is_not_applicable_without_any_read`.
- Undeterminable version, `_src_path` missing/foreign, answers file missing, no GitHub auth, failed release read, no tag, prerelease tag, unresolved project repository each fail with their cause: `test_undeterminable_inputs_fail_with_their_cause`; start stops before any branch: `test_undeterminable_release_lag_stops_task_start_before_any_branch_exists`.
- `_src_path` forms used by `rollout_project.EXPECTED_SOURCES` parse: `test_every_source_form_resolves_to_owner_and_name`.

## Correctness

- Pending-rollout reconciliation is unchanged and runs first; the lag check uses the config re-read after it.
- No fallback in the new code. The existing fail-open branches of `observe_pending_rollout` (no GitHub env, unresolved repository) are unchanged and out of scope; they are reported to the coordinator.

## Coherence

- Spec delta, design and tasks agree; the platform manifest is regenerated; existing start-path tests stub the new network read.

## Not verified / limits

- Not exercised against a live downstream project start; the GitHub reads are mocked.
