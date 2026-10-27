OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-config delta, proposal, design and tasks; registry check of six project configurations on 2026-10-27; targeted unit tests and a full `run_test_groups.py --all` run (18 groups, 0 failed) during the change; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner decision 2026-10-23 (variant B): missing file is an error, rendered keys are required and validated once at read time, defaults only for optional keys in one schema and in documentation.
- Coordinator decision 2026-10-27 (option A): the required set is the keys present in every managed project's configuration; `paths.pending_completed_worktree_cleanup` (absent in one managed project) is the only optional key, default `.claude/pending-completed-worktree-cleanup.json`. The contradictory accessor defaults for `protected_main` and `pr_merge_mode` are removed. A configuration error reaches the user as one line naming key, file and what to add.

## Completeness

- Configuration file is absent: `test_missing_file_is_an_explicit_error`.
- Required key is missing: `test_missing_required_key_names_key_file_and_line_to_add`, `test_missing_required_path_names_the_paths_table`.
- Required key has the wrong type: `test_wrong_type_names_key_and_expected_type`, `test_boolean_is_not_accepted_for_an_integer_key`.
- Optional key is absent: `test_optional_path_uses_the_schema_default_only_when_absent`.
- Accessors without substitutes: `test_accessors_return_validated_values_without_substitutes`.
- Source and template render every required key: `test_source_and_template_configurations_satisfy_the_schema`.
- One-line diagnostic at an entry point: `test_entry_point_reports_a_configuration_error_in_one_line`.
- Call sites: no `get(<required key>, <default>)` read of the platform configuration remains in `template/scripts` or `scripts` (grep over the required top-level keys and `[paths]` keys); remaining `.get("<key>")` reads without a default are existing explicit validations.

All tasks in `tasks.md` are complete; 3.3 is this receipt together with the selected checks.

## Correctness and coherence

- Test fixtures that wrote partial configurations or none now use `tests/_platform_config.py`. Fixtures that relied on the removed accessor defaults keep their meaning through explicit `protected_main = false` / `pr_merge_mode = "manual"`. Tests that asserted a silent default now assert the explicit error (select_checks main-branch and capability cases, publication-queue trust source without a project file, worktree-hygiene board cases, downstream operator `platform_version`, managed authoring without a file, task-freshness `paths.checks`).
- Compatibility: `.dev-platform.toml` stays project-owned (Copier `_skip_if_exists`; guarded rollout recopy changes only `platform_version`). All managed projects carry every required key. Excluded `cuby` and `planner-agent-lab` lack `scm_provider`, and `planner-agent-lab` also lacks `paths.main_merge_lock`, `paths.pending_worktrees`, `paths.friction_state` and `paths.friction_reports`; they must add these lines by hand when they upgrade (documented in `docs/project-owned-config.md`).
- Found and not changed: `scripts/rollout_project.py::_read_operator_config` treats an unreadable operator configuration as "not configured" (existing best-effort read, outside this slice); `platform_divergence.py` `main` calls `startswith` on `Problem` objects when protected-touch problems exist (seen only while the manifest was stale; latent, outside this slice).
