# Project-owned platform configuration

`.dev-platform.toml` is created by Project Factory for a fresh repository, then becomes project-owned configuration.

Managed Copier upgrades preserve the file rather than patching it wholesale. This allows reviewed project values such as `project_required_files`, workflow choices and future project-specific configuration to survive platform releases without template conflicts.

The platform may still migrate explicitly platform-owned fields through versioned bootstrap/migration code. Today `scripts/platform_bootstrap.py` synchronizes `platform_version` from the stable `.copier-answers.yml` `_commit` while preserving all project-owned values and surrounding tables. Development Backlog, fleet, rollout and other operator-only bindings are supplied through separately controlled operator configuration when an operator action needs them; bootstrap does not infer or add them from project metadata. `scripts/platform_doctor.py` and managed rollout both fail closed if stable-version records disagree.

This boundary means future additions to `.dev-platform.toml` must be backward-compatible in platform scripts: a new setting is optional, with its default defined once in the configuration schema below, until every managed project carries it; mandatory schema migrations belong in bootstrap/migration code rather than relying on Copier to overwrite an adopted project's config.

## Configuration schema

Platform scripts read `.dev-platform.toml` through `read_platform_config` /
`read_project_config` in `template/scripts/_platform_common.py`. The file is
validated once, at read time, against one schema defined there
(`PLATFORM_CONFIG_REQUIRED`, `PLATFORM_CONFIG_REQUIRED_TABLES`,
`PLATFORM_CONFIG_OPTIONAL_DEFAULTS`). Scripts then read keys directly and never
substitute their own defaults.

- A missing `.dev-platform.toml` is an error naming the file.
- A missing required key is an error naming the file, the key and the line to
  add, for example ``add `main_branch = "<value>"` ``.
- A required key with the wrong type (for example `protected_main = "yes"`) is
  an error naming the key and the expected type.

### Required keys

Top level:

| Key | Type |
| --- | --- |
| `schema_version` | integer |
| `platform_version`, `platform_ci_ref`, `project_name`, `project_slug` | non-empty string |
| `main_branch`, `workflow_profile`, `harness_mode` | non-empty string |
| `publish_mode`, `pr_merge_mode`, `scm_provider`, `agent_tools` | non-empty string |
| `protected_main` | boolean |

`[capabilities]`: `openspec`, `github_sync`, `feature_branches`, `worktrees`,
`agent_board`, `platform_git_lifecycle` (booleans).

`[paths]`: `worktrees`, `agent_board`, `main_merge_lock`, `pending_worktrees`,
`friction_log`, `friction_state`, `friction_reports`, `checks` (non-empty
strings).

### Optional keys with a schema default

| Key | Default |
| --- | --- |
| `paths.pending_completed_worktree_cleanup` | `.claude/pending-completed-worktree-cleanup.json` |

Optional tables such as `[operator]`, `[development_backlog]`,
`[private_lineage]`, `[model_routing]` and `[tools.*]` are read by their own
features and are not part of this schema.

### Upgrading an existing project

The template renders every key above, but `.dev-platform.toml` is
project-owned after creation: Copier lists it in `_skip_if_exists`, and the
guarded rollout recopy changes only `platform_version`. A project rendered
before a key existed keeps its old file. If an upgraded project stops with
"missing required key", add the named line to `.dev-platform.toml` using the
value from `template/.dev-platform.toml.jinja` (for `[paths]`, the template's
`.claude/...` path) and commit it with the upgrade.

A key joins the required set only when every managed project already carries
it; otherwise it stays optional here with its documented default.

## Shared-workspace permission contract

The rendered `scripts/shared_workspace.py` derives the shared group from the integration checkout (or the machine-local `DEV_PLATFORM_SHARED_GROUP` override). It checks and repairs only the registered lifecycle allowlist under `.claude` (board, locks, worktree administration, friction and routing state) plus required Git common-directory metadata. Unknown `.claude` entries, including tool-managed symlinks and transient caches, are foreign and untouched. `check` is read-only; `fix` sets group write and setgid only within those registered roots and stops with the exact path and owner action when repair is not authorized. Unsupported non-POSIX filesystems use a diagnostic no-op path.

`core.sharedRepository=group` is stable configuration owned by bootstrap/adoption and by an explicit repair (`scripts/shared_workspace.py fix`). Ordinary lifecycle preflight only *verifies* the value and never rewrites an already-correct setting, so independent task publications do not contend on `.git/config.lock`. When the value is genuinely missing or wrong, preflight performs the one-time repair through the existing serialized integration boundary (`.claude/main-merge.lock`) and rechecks it before the lifecycle continues. A registered path that disappears mid-audit because of ephemeral Git maintenance triggers a bounded re-scan rather than a false persistent failure; durable permission, ownership, symlink and foreign-state findings still fail closed.

Do not resolve a `.dev-platform.toml` rollout conflict by blindly taking the template version. Preserve reviewed project configuration and use the platform migration path for platform-owned fields.
