## Context

- `template/.dev-platform.toml.jinja` renders the configuration once; `copier.yml` lists `.dev-platform.toml` in `_skip_if_exists` and `scripts/rollout_project.py::require_platform_config_contract` refuses any change beyond `platform_version` during guarded recopy. Existing projects never receive new keys from the template.
- Registry check on 2026-10-27 (6 repositories): every project has `schema_version`, `platform_version`, `platform_ci_ref`, `project_name`, `project_slug`, `main_branch`, `workflow_profile`, `harness_mode`, `protected_main`, `publish_mode`, `pr_merge_mode`, `agent_tools`, the six `[capabilities]` flags and `paths.worktrees/agent_board/friction_log/checks`. Managed `Jara_Fin` lacks `paths.pending_completed_worktree_cleanup`; excluded `cuby` and `planner-agent-lab` lack `scm_provider`; excluded `planner-agent-lab` also lacks `paths.main_merge_lock/pending_worktrees/friction_state/friction_reports`.
- Operator configuration is merged after the project file and may not override lifecycle identity keys.

## Decisions

- **Required set = keys present in every managed project** (coordinator option A, inside the owner's variant B). Top-level: `schema_version` (int), `platform_version`, `platform_ci_ref`, `project_name`, `project_slug`, `main_branch`, `workflow_profile`, `harness_mode`, `publish_mode`, `pr_merge_mode`, `scm_provider`, `agent_tools` (str), `protected_main` (bool). `[capabilities]`: `openspec`, `github_sync`, `feature_branches`, `worktrees`, `agent_board`, `platform_git_lifecycle` (bool). `[paths]`: `worktrees`, `agent_board`, `main_merge_lock`, `pending_worktrees`, `friction_log`, `friction_state`, `friction_reports`, `checks` (str).
- **One optional key**: `paths.pending_completed_worktree_cleanup`, default `.claude/pending-completed-worktree-cleanup.json`, filled by `read_platform_config` from the schema. Managed `Jara_Fin` predates it and rollout cannot add it.
- **Validate once, at read time.** The project file is validated before the operator merge; callers index required keys directly. A failure is a `PlatformConfigError` (a `RuntimeError`) naming the file, the key and the line to add, for example `add main_branch = "main"`.
- **One-line diagnostics at every entry point.** `_platform_common` installs a `sys.excepthook` that prints an uncaught `PlatformConfigError` as one line (`platform configuration error: ...`) and lets the interpreter exit non-zero; any other exception keeps the default report. Every platform entry point imports the module, so no per-script wrapper is needed and nothing is caught or substituted.
- **No accessor substitutes.** `protected_main` and `pr_merge_mode` lose their contradictory defaults; the accessors return the validated values.
- **Other repositories' configs** read by rollout and doctor helpers through their own loaders keep their behavior unless they read a required key with a default, which becomes a direct read after the same validation.

## Risks

- Tests that write partial configurations or none fail; a shared complete-config fixture replaces them.
- Excluded projects upgrading later stop with a named error until the missing keys are added; documented in the PR and release note.
