## Why

The accepted Requirement routing contract made connected ChatGPT fixation read `[development_backlog]` only from the target repository's committed `.dev-platform.toml`, and stop when that file is absent. An operator-enabled checkout keeps `.dev-platform.toml` untracked by design, and the public snapshot excludes it. So for an operator-managed target such as Dev Platform itself, GitHub never has the file, and connected ChatGPT can no longer create Requirements for that target at all.

## What Changes

- Connected routing resolution becomes ordered. Committed target `[development_backlog]` is used when it exists. Otherwise the operator-declared Project parameters are used; the protocol already requires `BACKLOG_REPOSITORY` and `TARGET_REPOSITORY` + `PROJECT_LABEL`, and this adds `DEFAULT_PRIORITY`, which mirrors `development_backlog.default_priority`. When both are declared and disagree, the result is a conflict. When neither is complete, nothing is created.
- `requirement_intake.py routing-parameters` renders exactly those Project parameters from `managed_task.authoring_config` and the checkout origin. The parameters are derived from the existing configuration and never hand-authored, so no second routing source is introduced.
- `requirement_intake.py` gains a pure reference resolver `resolve_connected_routing` and a shared pure label check used by both the local read-back and the connected reference path.
- Local `create` behavior, the P0–P3 scale, Incubator and managed technical authoring are unchanged.

## Impact

`template/scripts/requirement_intake.py`, `tests/test_requirement_intake.py`, a new connected-routing fixture, `docs/engineering/chatgpt-project-protocol.md` (central and template copy), and the managed-task-intake spec.
