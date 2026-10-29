## Why

In a project whose task root is its integration copy (`standalone-clone`, e.g. `execute_requirement.py advance` run in the main copy of agent-control-room on v2.0.0), the retained outcome can never be recorded after implementation: `record_retained_execution` runs `_postcheck`, which compares the copy with the pre-implementation snapshot, and any implementation commit moves HEAD past `origin/main` and fails as a delegated-write-containment violation. Archive needs both a committed package and the recorded outcome, so the task cannot finish (BR-896, found on the 2026-10-28 board slice). The existing test records the outcome straight after `prepare`, without commits. Separately, shipped hints and docs name `scripts/dogfood_task.py` and `route-codex`/`route-claude`, which a rendered project does not have, `model-routing.md` says the outcome is recorded after implementation while the code forbids it, and `.managed-task-state.json` is described as ignored but is not ignored by a project's `.gitignore`.

## What Changes

- `_postcheck` for a `standalone-clone` route with no delegated child accepts implementation commits made after `prepare`: HEAD may advance only as a descendant of the snapshot HEAD. Everything else stays a violation: a HEAD that is not a descendant, uncommitted or untracked paths other than platform lifecycle records, and any change to a path that was already dirty at the snapshot. The accepted advance is recorded as `task_commits` (before, after, count).
- Hints in `model_routing.py`, `independent_review_runner.py`, `blocking-gates.toml` and the shipped docs name `model_routing.py prepare` / `begin-claude-delegation` instead of `dogfood_task.py` and `route-codex`/`route-claude`.
- `managed_task` makes `.managed-task-state.json` locally ignored (`.git/info/exclude`, idempotent, an explicit error when it cannot) instead of relying on a project `.gitignore`.
- `template/docs/engineering/model-routing.md` describes the standalone-clone postcheck as implemented.

## Impact

- `template/scripts/model_routing.py`, `managed_task.py`, `independent_review_runner.py`, `template/dev-platform/blocking-gates.toml`, `template/docs/engineering/{model-routing,openspec-workflow}.md`, tests, platform manifest.
- Spec: model-routing (added requirement).
