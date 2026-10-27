## Why

`read_platform_config` silently returns a built-in configuration when `.dev-platform.toml` is absent, and about seventy call sites read required keys through `get(<key>, <default>)`. A project with a missing or misspelled key therefore runs on substituted values instead of failing, and the substitutes disagree with each other: without the file `protected_main` is `true` and `pr_merge_mode` is `auto`, while the accessors default them to `false` and `manual`. The owner decided (2026-10-23, variant B) that a missing file is an explicit error, rendered keys are required and validated once at read time, and defaults exist only for truly optional keys, defined in one schema and documented.

## What Changes

- `template/scripts/_platform_common.py`: one schema (`PLATFORM_CONFIG_REQUIRED`, `PLATFORM_CONFIG_REQUIRED_TABLES`, `PLATFORM_CONFIG_OPTIONAL_DEFAULTS`) of required top-level keys, required `[capabilities]` flags, required `[paths]` entries and the optional `paths.pending_completed_worktree_cleanup` with its default. `read_platform_config` raises on a missing file, a missing required key or a wrong type, naming the key, the file and what to add; it fills only the documented optional default. Accessors (`workflow_profile`, `harness_mode`, `protected_main`, `publish_mode`, `pr_merge_mode`, `scm_provider`) read without substitutes. `read_project_config` (the committed file without operator overrides, used by the publication-queue trust check) validates the same schema and fails on a missing file instead of returning `{}`.
- Every `template/scripts` and `scripts` reader of a required key reads it directly; per-call-site defaults and the duplicated path-default table in `shared_workspace.py` are removed.
- `docs/project-owned-config.md` (schema section, linked from `docs/adoption.md`): required keys, the one optional key with its default, and the upgrade step for an older project.
- Raw `.dev-platform.toml` loaders that bypassed the reader (`dev.py`, `platform_bootstrap.py`, `shared_workspace.py`, `requirement_integration.py`) use the validated reader; `agent_friction.non_task_names` no longer swallows a configuration failure; the rollout's loader for another project's file requires the two keys it reads (`platform_version`, `harness_mode`). The parallel-lifecycle acceptance scenario seeds a complete configuration. An uncaught configuration error is printed as one line by every entry point.
- Tests: a shared complete-config fixture; tests for missing file, missing key, wrong type and the optional default.

## Impact

- About 27 files under `template/scripts/` and `scripts/`, plus tests writing partial configurations.
- Spec: platform-config (one added requirement).
- Release: a project whose `.dev-platform.toml` lacks a required key stops with a named error after upgrade. All managed projects carry the keys; excluded `cuby` and `planner-agent-lab` lack `scm_provider` (and `planner-agent-lab` several `[paths]` entries) and must add them by hand at upgrade. This affects release classification.
