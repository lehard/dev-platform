## Context

- `start_worktree.create_worktree` is the single creation point for multi-agent task worktrees (`start_task.py`, managed start through `start_task`). It runs `git worktree add`, copies an untracked local `.dev-platform.toml`, re-runs the shared-workspace `preflight(root)` (which repairs registered paths, including `.git/worktrees/**`), then registers the board item; any exception rolls back the worktree and branch.
- `capability_manager.py sync` is idempotent, writes only owned marker files under `.claude/skills` / `.codex/skills` of the checkout it runs in, and removes only unselected owned surfaces. Its `audit` is what the doctor runs.
- Both `scripts/capability_manager.py` and `dev-platform/capabilities.toml` are in the doctor's required-file list, so every valid checkout has them.
- Git reads ignore rules only from `$GIT_COMMON_DIR/info/exclude`; a linked worktree's `--git-dir` has no `info` directory unless something creates it.

## Decisions

1. **Sync at creation, inside the new worktree.** After `git worktree add` and the config copy, run `python3 scripts/capability_manager.py sync` with `cwd=worktree`, inside the existing guarded block so failure triggers the existing rollback. The new worktree is created by the starting user, so ownership of the integration `.claude/skills` is irrelevant. A non-zero exit raises `RuntimeError` naming the worktree, the manager output and the repair route: fix the reported cause, then re-run the start; `python3 scripts/capability_manager.py sync` is the command to reproduce the step. No skip path, no partial continuation.
2. **Sync before the shared-workspace recheck.** The existing post-add `preflight(root)` stays after sync, so creation ends with a verified shared contract for every registered path.
3. **Excludes go to the common directory.** `dev.py` uses `git rev-parse --path-format=absolute --git-path info/exclude`. In the integration checkout this is the same file as before; in a linked worktree it is the common file Git actually reads, so the rule now takes effect and no per-worktree `info` directory is created. Behavior is otherwise unchanged (idempotent append).
4. **Doctor stays diagnostic-only but names the command.** The capability-audit failure line appends `run python3 scripts/capability_manager.py sync`. The doctor does not repair.

## Rejected alternatives

- Make the doctor auto-sync or downgrade the audit to a warning: hides a real mismatch and violates diagnostic-only doctor.
- Copy `.claude/skills` from the integration checkout: copies foreign/stale state and breaks when that directory belongs to another OS user.
- Chmod the per-worktree `info` directory after `dev.py` creates it: repairs a symptom of writing to a file Git ignores.

## Risks and mitigations

- *Start becomes slower.* Sync is local file rendering of a handful of descriptors; negligible.
- *A broken descriptor now blocks start instead of the first check.* Intended by the Requirement: fail early with the cause.
- *Projects whose rendered `dev.py` already created per-worktree `info` directories.* Existing directories are untouched; the shared-workspace preflight of lifecycle steps continues to report/repair them as today.
