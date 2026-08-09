# Design

## Ownership boundary

Copier continues to create the initial repository contract, but files whose contents are expected to evolve per project are treated as project-owned after creation:

- `AGENTS.md`
- `README.md`
- `dev-platform/checks.toml`
- `openspec/config.yaml`
- `docs/engineering/project-rules.md` (already project-owned)

These files are added to Copier `_skip_if_exists`, so fresh repositories receive defaults and existing repositories keep their reviewed local content during upgrades.

Shared behavior that must evolve centrally remains in platform-managed scripts and managed workflow/runbook files.

## Version invariant

`platform_bootstrap.py` reads `_commit` from `.copier-answers.yml` after Copier renders/updates the project. When `_commit` is a stable `vX.Y.Z`, it rewrites the top-level `platform_version` in `.dev-platform.toml` to `X.Y.Z`.

`rollout_project.py` then validates both metadata sources after Copier update and blocks if they differ.

## Project-specific doctor requirements

`.dev-platform.toml` gains `project_required_files = []` at top level. `platform_doctor.py` appends those entries to the shared required-file list. This keeps the executable doctor centrally managed while projects can declare extra required compatibility helpers without editing shared doctor code.

## Rollout behavior

The rollout remains fail-closed. Project-owned files are never silently rewritten by managed rollout. Any conflict in genuinely platform-managed files remains blocking and must be resolved through a reviewed migration.
