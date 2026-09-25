## Why

`requirement_intake.py create` labels a new Business Requirement only with `type:requirement`. Managed technical tasks already derive `project:*` and `priority:*` from `[development_backlog].project_label` and `default_priority`, but Requirements skip that routing, so their shared-board cards lack project and priority and the operator cleans them up by hand. The connected ChatGPT Project adapter mirrors the same gap.

## What Changes

- `requirement_intake.py create` resolves Backlog routing from the existing `managed_task.authoring_config` (`[development_backlog]`): the project label for the checkout's origin repository and `default_priority` unless an explicit `--priority P0..P3` is given. No new configuration key or default is introduced.
- Routing fails closed before any mutation when `--target-repository` is not the checkout's origin repository (its project label is not configured here), when `--repository` disagrees with `development_backlog.repository`, or when a configured label is unavailable in the Backlog.
- The Issue is created with `type:requirement`, the project label and the priority label, then read back. Only missing expected labels are completed on that exact Issue; any other `project:*`/`priority:*` label or a still-incomplete label set is reported with the exact Issue reference and never reported as success.
- The ChatGPT Project protocol requires the same labels, resolved from the target repository's committed `.dev-platform.toml`, and the same read-back before fixation succeeds.
- Incubator semantics, internal-change lifecycle and the P0–P3 scale are unchanged.

## Impact

`template/scripts/requirement_intake.py`, its tests, `docs/engineering/chatgpt-project-protocol.md` (central and template copy) and `task-intake.md` (central and template). Existing Requirements are not relabelled. The `create` CLI gains an optional `--priority`; existing flags stay compatible.
