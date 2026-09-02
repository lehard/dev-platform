# Project-owned platform configuration

`.dev-platform.toml` is created by Project Factory for a fresh repository, then becomes project-owned configuration.

Managed Copier upgrades preserve the file rather than patching it wholesale. This allows reviewed project values such as `project_required_files`, workflow choices and future project-specific configuration to survive platform releases without template conflicts.

The platform may still migrate explicitly platform-owned fields through versioned bootstrap/migration code. Today `scripts/platform_bootstrap.py` synchronizes `platform_version` from the stable `.copier-answers.yml` `_commit`, adds the missing `[development_backlog]` authoring section from the existing safe `project_slug`, and adds only missing `project_owner`/`project_number` locator keys to an existing backlog table. It preserves all existing project-owned values and surrounding tables. `scripts/platform_doctor.py` and managed rollout both fail closed if stable-version records disagree.

This boundary means future additions to `.dev-platform.toml` must be backward-compatible in platform scripts: new optional settings need safe defaults, and mandatory schema migrations belong in bootstrap/migration code rather than relying on Copier to overwrite an adopted project's config.

## Shared-workspace permission contract

The rendered `scripts/shared_workspace.py` derives the shared group from the integration checkout (or the machine-local `DEV_PLATFORM_SHARED_GROUP` override). It checks and repairs only the registered lifecycle allowlist under `.claude` (board, locks, worktree administration, friction and routing state) plus required Git common-directory metadata. Unknown `.claude` entries, including tool-managed symlinks and transient caches, are foreign and untouched. `check` is read-only; `fix` sets group write and setgid only within those registered roots and stops with the exact path and owner action when repair is not authorized. Unsupported non-POSIX filesystems use a diagnostic no-op path.

`core.sharedRepository=group` is stable configuration owned by bootstrap/adoption and by an explicit repair (`scripts/shared_workspace.py fix`). Ordinary lifecycle preflight only *verifies* the value and never rewrites an already-correct setting, so independent task publications do not contend on `.git/config.lock`. When the value is genuinely missing or wrong, preflight performs the one-time repair through the existing serialized integration boundary (`.claude/main-merge.lock`) and rechecks it before the lifecycle continues. A registered path that disappears mid-audit because of ephemeral Git maintenance triggers a bounded re-scan rather than a false persistent failure; durable permission, ownership, symlink and foreign-state findings still fail closed.

Do not resolve a `.dev-platform.toml` rollout conflict by blindly taking the template version. Preserve reviewed project configuration and use the platform migration path for platform-owned fields.
