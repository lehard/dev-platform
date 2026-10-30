## Why

Since 2026-10-28 releases no longer dispatch managed rollout; a project is updated on demand through Roll Out Platform (`rollout.yml` with `repository=owner/name`). `rollout_preflight` at task start only reconciles an open rollout PR, so without one a task silently starts on an older platform release and the owner learns about the lag by accident (BR-843).

## What Changes

- `rollout_preflight.observe_platform_lag(root, config, env)` reads the project's `platform_version`, resolves the platform source repository from `.copier-answers.yml` `_src_path`, reads that repository's latest published release and the project's GitHub repository, and returns `current`, `behind` (with the exact `gh workflow run rollout.yml --repo <source> -f version=<latest> -f repository=<project>` command) or `not-applicable` for the platform source itself. Anything it cannot determine raises `PlatformLagError` naming the cause.
- `start_task` evaluates it after pending-rollout reconciliation (re-reading the config a merged rollout may have changed) and prints the lag report when behind; it continues the start.

## Impact

- `template/scripts/rollout_preflight.py`, `template/scripts/start_task.py`, tests, platform manifest.
- Spec: platform-lifecycle (new requirement).
