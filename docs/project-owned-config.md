# Project-owned platform configuration

`.dev-platform.toml` is created by Project Factory for a fresh repository, then becomes project-owned configuration.

Managed Copier upgrades preserve the file rather than patching it wholesale. This allows reviewed project values such as `project_required_files`, workflow choices and future project-specific configuration to survive platform releases without template conflicts.

The platform may still migrate explicitly platform-owned fields through versioned bootstrap/migration code. Today `scripts/platform_bootstrap.py` synchronizes `platform_version` from the stable `.copier-answers.yml` `_commit`, adds the missing `[development_backlog]` authoring section from the existing safe `project_slug`, and adds only missing `project_owner`/`project_number` locator keys to an existing backlog table. It preserves all existing project-owned values and surrounding tables. `scripts/platform_doctor.py` and managed rollout both fail closed if stable-version records disagree.

This boundary means future additions to `.dev-platform.toml` must be backward-compatible in platform scripts: new optional settings need safe defaults, and mandatory schema migrations belong in bootstrap/migration code rather than relying on Copier to overwrite an adopted project's config.

Do not resolve a `.dev-platform.toml` rollout conflict by blindly taking the template version. Preserve reviewed project configuration and use the platform migration path for platform-owned fields.
