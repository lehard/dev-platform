OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-config delta, proposal, design and tasks; registry check of six project configurations on 2026-10-27; targeted unit tests and a full `run_test_groups.py --all` run (18 groups, 0 failed) during the change; repository-owned selected checks recorded by the lifecycle; after the integration failure, a CI-equivalent run (clean export without `.dev-platform.toml`, source contract installed as in CI: `check_ci_python.py` and full `run_test_groups.py --all`, 18 groups, 0 failed) plus the CI smoke steps `upgrade_smoke.py` (three profiles) and `rollout_recopy_smoke.py` in the task worktree, which has the release tag history the clean export lacks
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

## Integration repair

- Required check `validate` failed on the integrated head: the central checkout keeps `.dev-platform.toml` untracked, CI did not install a contract, and the unit-test runner had relied on the removed missing-file defaults. `ci.yml` now installs `dev-platform/source-contract.toml` before the first platform script (same step as `lifecycle-workers.yml` and `publication-queue.yml`), and the contract gains `agent_tools`, otherwise the hosted workers would fail the schema after merge.
- Workflows checked by running their commands in a clean export without the file, or by reading the scripts they call: `ci.yml` (`run_test_groups.py` fails without a contract; the rest do not read it), `explorer.yml`, `code-erosion.yml`, `publish-version.yml`, `friction-close-on-merge.yml` (`close-fixed` uses GitHub only), `rollout.yml`, `reconcile-stale-rollouts.yml`, `adopt-project.yml` (registry passed explicitly; target projects carry their own file). `project-ci.yml` runs in rendered projects with a committed file.
- `test_source_and_template_configurations_satisfy_the_schema` validates `dev-platform/source-contract.toml`.

## Review repair

- Material review finding `friction-changed-paths-main-fallback`: `agent_friction.changed_paths` caught any exception from the configuration read and assumed `main`. The catch is removed; a missing or incomplete configuration now propagates the schema diagnostic (`ChangedPathsConfigurationTests.test_missing_or_incomplete_configuration_is_an_explicit_error`). An unreadable git diff still returns the documented "unknowable" result.
- Advisory review notes (excepthook installed at import, `_project_topology` schema strictness, the `sandboxed_writer_probes.py` fixture, `capability_manager` reading `agent_tools`) are carried to the next slice.
