# Preserve project-owned platform config

## Why

The second live Planner Lab rollout proved that project-owned AGENTS/README/check/OpenSpec files and the shared doctor now upgrade cleanly, but `.dev-platform.toml` still conflicts when a project stores reviewed project-specific configuration such as `project_required_files`.

## What changes

- Treat `.dev-platform.toml` as project-owned after its initial Project Factory render.
- Keep platform-owned mutable fields, especially `platform_version`, synchronized through bootstrap/migration logic rather than whole-file Copier patching.
- Extend upgrade smoke and documentation to cover this boundary.

## Non-goals

- Do not weaken version-coherence validation.
- Do not auto-resolve arbitrary configuration conflicts.

## Definition of Done

- A downstream customization in `.dev-platform.toml` survives Copier update without `.rej`.
- Bootstrap still advances `platform_version` to the exact Copier release.
- Platform CI and strict OpenSpec validation pass.
