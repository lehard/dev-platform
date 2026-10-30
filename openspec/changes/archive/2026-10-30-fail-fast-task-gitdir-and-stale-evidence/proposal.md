## Why

`finish` keeps failing at publication after the full ~25-minute validation (2026-10-29; PRs #801, #804, #805; root friction lehard/dev-platform#79): local source admission (`local_workspace.audit` via `shared_workspace._admit_local_source`, run by `project_publish` before push) refuses `.git/worktrees/<slug>/dev-platform` (mode 0775, no setgid). The BR-919 lifecycle preflight passed in the same run because that directory did not exist yet: `select_checks.write_evidence` creates it during validation with a plain `mkdir` (APFS does not inherit setgid) and writes the evidence file with the process umask. In addition, the preflight's admission step refuses own-account findings instead of repairing them, unlike its registered-path step.

Separately (lehard/dev-platform#803), after `reconcile` merges a moved main that touched a task path, committed selected-check evidence no longer proves the task content; this is found only by the later evidence gate, whose message does not name the refresh command.

## What Changes

- `task_content_identity.ensure_quick_evidence_directory(root)` creates the task git dir's evidence directory under the shared contract; `start_worktree.create_worktree` calls it for every new task worktree.
- `select_checks.write_evidence` writes through `shared_workspace.atomic_write_text` (group rw file, group rwx+setgid parent) instead of `mkdir` + `write_text`.
- `local_workspace.admit_repairing(root)` runs the same `audit` publication runs, repairs findings on paths the current account owns and raises for the rest; `shared_workspace.preflight_with_report` uses it and reports those paths as repaired.
- `openspec_lifecycle.stale_committed_evidence(root)` decides, with the content-proof comparison the evidence gate uses, whether committed managed evidence is bound to content the task no longer has, and returns a message with the exact refresh command. `task_reconciliation.reconcile` fails with it after a successful merge; a new lifecycle preflight condition `task-evidence` refuses with it.

## Impact

- `template/scripts/{task_content_identity,start_worktree,select_checks,local_workspace,shared_workspace,lifecycle_preflight,openspec_lifecycle,task_reconciliation}.py`, `template/dev-platform/blocking-gates.toml` (catalog entry naming the new condition), tests, platform manifest.
- Specs: shared-workspace (preflight requirement modified; evidence path creation added), completion-lifecycle (shared preflight requirement modified; stale-evidence detection added).
