OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle and gate-fail-explicit deltas, proposal, design and tasks; targeted unit tests; `openspec validate --strict`; repository-owned selected checks recorded by the lifecycle; local `public_distribution_snapshot_smoke.py` at candidate stage
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner decision 2026-10-27 (variant A): the private-reference guard is mandatory where `private_lineage.enabled` and reports "not applicable by configuration" elsewhere.
- Coordinator 2026-10-28: the slice is split; `github_retry_attempts`, the review advisories and `AGENTS.md` move to the next slice.

## Completeness

- Guard missing with private lineage enabled (finish and publish): `GuardByConfigurationTests.test_enabled_without_guard_blocks_finish_and_publish`.
- Private lineage not enabled: `test_disabled_reports_not_applicable_and_runs_nothing` (no subprocess, one not-applicable line per caller).
- Private reference with the guard present: `test_enabled_with_guard_blocks_a_private_reference_in_the_title`; end-to-end `test_private_reference_preflight_blocks_evidence_and_commit_before_validation` and `test_clean_preflight_streams_stage_and_validation_progress_then_publishes` now enable private lineage; `test_head_race_and_privacy_guard_block_edits` enables it for the publish recheck.
- Task branch without `--base`: `ChangedFileBaseTests.test_task_branch_without_base_uses_origin_main`.
- Main branch / detached HEAD without `--base`: `test_main_branch_without_base_fails_naming_the_options`, `test_detached_head_without_base_fails`.
- Git diff fails: `test_failing_git_diff_is_an_error`.
- Wrapper resolves the base before the selector: `test_central_wrapper_resolves_the_base_before_the_selector`.
- Friction staleness: reproduced as a swallowed exception; `test_unreadable_task_state_is_an_error_not_a_stale_checkpoint`, `test_quick_task_has_no_content_proof`; existing `test_checkpoint_content_proof_survives_lifecycle_only_head_change` and `test_checkpoint_content_proof_rejects_task_mutation` still pass.

## Correctness

- Every platform caller of `select_checks.py` passes `--base` or protected-full (`finish_task`, `openspec_lifecycle`, `post_review_finalization`, `adopt_project`, `project-ci.yml`), so the removed fallback changes no lifecycle path.
- CI installs the source contract without `[private_lineage]`; the CI `validate` job runs `scripts/check_private_backlog_refs.py` directly and the publication queue does not call these guards, so CI privacy coverage is unchanged.

## Coherence

- `docs/engineering/agent-workflow.md` documents the base rule; `docs/engineering/openspec-workflow.md` the guard rule for finish and publication.

## Test adaptation

- The first full run failed in two groups: the Explorer drift hook tests used the wrapper's old argv-based `surface_explorer_drift`, and skeletal `publish_pr` tests use roots without a platform configuration, which the configuration-based guard now reads. The hook tests now exercise `drift_base` and `surface_explorer_drift(base)`; the skeletal tests patch only the guard decision, which `GuardByConfigurationTests` covers. The rerun of both groups, the candidate-stage snapshot smoke (18 groups) and the full selected-check run passed.

## Noticed, not changed

- `task_content_identity.content_identity` returns `None` on a failing `git merge-base`/`git diff`; callers then report "could not be proven equivalent" (named, not silent; outside this slice).
