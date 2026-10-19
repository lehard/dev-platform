## Why

A freshly started task worktree repeatedly fails its first `select_checks --execute` or archive on `platform_doctor` (recorded at least five times): the selected capabilities' derived provider surfaces (`.claude/skills/dev-platform-*`, `.codex/skills/dev-platform-*`) are gitignored and therefore absent, and the worktree's Git administrative `info` directory lacks group rwx+setgid. Each time an agent repairs it by hand with `capability_manager.py sync` and `shared_workspace.py fix`; the doctor hint does not name the command.

Two root causes are confirmed from code:

- `start_worktree.create_worktree` (used by `start_task.py` and managed start) never runs capability sync in the new checkout. Generated CI already does this for fresh checkouts; local task start does not.
- `dev.py ensure_local_generated_excludes` resolves `info/exclude` under `git rev-parse --git-dir`, which in a linked worktree is `.git/worktrees/<name>`. Git never reads that file (it reads `$GIT_COMMON_DIR/info/exclude`), and creating it materializes a per-worktree `info` directory under the default umask, outside the shared-workspace contract that the doctor audits.

## What Changes

- Task worktree creation runs `scripts/capability_manager.py sync` inside the new worktree after the checkout and local config copy, before the shared-workspace recheck and board registration. A sync failure aborts the start with the cause and the repair command, and the existing rollback removes the partial worktree and branch.
- `dev.py` writes generated-integration excludes to `git rev-parse --git-path info/exclude` (the common directory Git actually reads), so it no longer creates a per-worktree `info` directory.
- The doctor's capability-audit failure names `python3 scripts/capability_manager.py sync`.

## Capabilities

### Modified Capabilities

- `engineering-capabilities`: local task worktree start materializes derived surfaces; the doctor names the repair command.
- `shared-workspace-safety`: platform writers do not create non-shared per-worktree Git administrative paths.

## Impact

`template/scripts/start_worktree.py`, `template/scripts/dev.py`, `template/scripts/platform_doctor.py`, their tests, platform manifest. Ships to managed projects through the normal release; no config, schema or capability content change.

## Non-goals

Changing capability selection or content; repairing files owned by another OS account outside the created worktree (integration `.claude/skills` ownership); new fallback or auto-repair inside the doctor (it stays diagnostic-only).
