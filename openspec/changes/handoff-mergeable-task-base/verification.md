OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the delegated executor's diff against the handoff-mergeable-task-base delta, proposal, design and tasks; targeted unit tests; repository-owned selected checks on the candidate head
Automated-Checks-Evidence: automated-checks.json

## Implementation

A delegated native Claude executor (standard route, sonnet) wrote all content. An earlier supervisor-written draft was withdrawn by a restoring commit before delegation, because the routed plan is a delegated child. The supervisor reviewed the diff and found one fail-open edge: `git merge-tree` exiting 1 without naming a path was classified behind-mergeable. The same executor fixed it to fail closed and added a regression test. Containment postcheck: clean.

- `template/scripts/_platform_common.py`:
  - `generated_files(root, commit)` reads `[[generated_files]]` (`path`, `regenerate` argv containing `{tree}`) from the check configuration named by `paths.checks`, at an exact commit, via `git show`. It raises `TaskFreshnessError` for a missing or non-relative `paths.checks`, a file absent at the commit, invalid TOML, a wrong table shape, a non-relative path, a duplicate path, or an invalid `regenerate`. No table means none.
  - `classify_task_base_currency`:
    - A clean trial merge gives `behind-mergeable`, with `overlapping` listing paths changed on both sides.
    - On a conflict, declarations are read from the observed main commit only. If every named conflict is declared generated, the result is `behind-mergeable` with `generated_conflicts`.
    - Otherwise the result is `reconcile-required`, naming only the real conflicts. A conflict with no named path is also `reconcile-required`.
  - `evidence()` records `{contract: behind-mergeable, main, base, overlapping, generated_conflicts}`.
- `select_checks.py`, `project_publish.py`, `finish_task.py`, `task_reconciliation.py` use the renamed state. Non-coordinator paths are unchanged.
- `dev-platform/checks.toml` declares `template/dev-platform/platform-manifest.json` with `python3 scripts/generate_platform_manifest.py --write --root {tree}`.
- `scripts/generate_platform_manifest.py` gains `--root`, which rebinds the tree paths and fails explicitly without `template/`.
- `docs/engineering/agent-workflow.md` describes the contract and the declaration.
- The manifest is regenerated.

## Completeness

Each delta scenario and the tests that cover it. Tests are in `tests/test_task_freshness.py` unless noted.

- Generated manifest conflict only, handed off:
  - `test_a_conflict_only_in_a_file_main_declares_generated_is_behind_mergeable`
  - `test_select_checks.py` generated-conflict evidence test
- Disjoint main handed off, with the contract recorded in evidence:
  - `test_disjoint_main_with_a_clean_trial_merge_is_behind_mergeable`
  - `test_developer_handoff_pushes_a_behind_mergeable_candidate_and_names_the_contract`
  - `test_select_checks.py` mergeable-contract evidence test
- Clean overlap of an ordinary file handed off:
  - `test_a_file_both_sides_changed_that_merges_cleanly_is_behind_mergeable`
  - `test_a_rename_on_main_counts_its_old_path_and_merges_cleanly`
  - `test_select_checks.py` clean-overlap test
- Real conflict blocks before expensive commands, naming the files and the reconcile command:
  - `test_a_real_conflict_requires_reconcile_naming_the_file`
  - `test_a_generated_conflict_beside_a_real_one_names_only_the_real_one`
  - `test_handoff_gate_names_the_overlap_and_the_reconcile_command`
  - `test_developer_handoff_of_an_overlapping_candidate_is_blocked_before_push`
  - `test_trial_merge_conflict_without_named_paths_fails_closed`
  - `test_select_checks.py` blocked-before-any-command test
- A candidate cannot declare its own conflict generated:
  - `test_a_declaration_added_only_by_the_candidate_does_not_apply`
- Malformed or missing declaration fails explicitly:
  - `test_a_malformed_declaration_at_main_fails_explicitly_for_a_conflict`
  - `test_missing_check_configuration_at_main_fails_explicitly_for_a_conflict`
  - `test_missing_paths_checks_key_fails_explicitly_for_a_conflict`
  - `test_generated_file_reader_rejects_each_malformed_shape`
  - `test_generated_file_reader_returns_declarations_and_none_without_a_table`
- Status:
  - `test_status_reports_behind_mergeable_candidate_without_reconcile_or_moving_origin_main`
  - `test_status_of_an_overlapping_candidate_requires_reconcile_and_names_the_file`
- Non-coordinator task keeps the fresh-base rule:
  - `test_publication_outside_the_coordinator_handoff_keeps_the_fresh_base_rule`
  - `test_status_of_a_non_candidate_behind_main_still_requires_reconcile`
  - `test_handoff_gate_accepts_behind_mergeable_only_for_a_coordinator_candidate`
- Generator `--root`: `PlatformManifestRootTests` in `tests/test_platform_manifest.py`.

## Correctness and coherence

- The declaration is never read from the candidate head or working tree.
- Re-admission uses the same gate through `project_publish.push_feature_branch` and `select_checks`.
- Earlier `behind-disjoint` evidence stays valid. No reader validates the `task_base` contract name: a search over `template/scripts` and `scripts` found none.
- Until queue-regenerates-generated-files lands, a candidate admitted with a manifest conflict reaches the existing integration repair. No gate is weakened.
- Existing fallbacks were noticed and left unchanged, as they are out of scope:
  - `task_reconciliation.observe` uses `config.get("main_branch", "main")`.
  - `select_checks.load_config` defaults `paths.checks`.

## Checks

- Targeted tests, run with the machine pool unset: `test_task_freshness`, `test_select_checks` and `test_platform_manifest` passed (OK). `test_task_reconciliation`, `test_protected_publish_contract`, `test_finish_merged_queue`, `test_platform_divergence`, `test_template_contract` and `test_git_lifecycle` passed (133 tests, OK).
- Repository-owned selected checks: `select_checks.py --base origin/main --execute --contribution-base 50d12669d77b7fc569083a25400191586294d940 --evidence openspec/changes/handoff-mergeable-task-base/automated-checks.json`. Outcome: success (compileall, ruff, `run_test_groups.py --all`; affected precheck success), recorded in `automated-checks.json` for the final task content.
