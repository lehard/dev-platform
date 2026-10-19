## 1. Worktree start

- [x] 1.1 In `template/scripts/start_worktree.py`, run `scripts/capability_manager.py sync` in the new worktree after the config copy and before the shared-workspace recheck, inside the rollback-guarded block; on failure raise with worktree, output and repair command.

## 2. Exclude writer

- [x] 2.1 In `template/scripts/dev.py`, resolve the exclude file with `git rev-parse --path-format=absolute --git-path info/exclude`.

## 3. Doctor hint

- [x] 3.1 In `template/scripts/platform_doctor.py`, append the `python3 scripts/capability_manager.py sync` command to the capability-audit failure.

## 4. Tests

- [x] 4.1 Linked-worktree test: ensuring excludes writes the common file and creates no per-worktree `info` directory.
- [x] 4.2 Worktree start test: selected capability surfaces exist after start; a failing sync aborts start, rolls back worktree and branch, and names the repair command.
- [x] 4.3 Doctor test: capability-audit failure names the sync command.

## 5. Verification and delivery

- [ ] 5.1 Regenerate the platform manifest; required platform checks; truthful semantic verification; archive; retrospectives; publication.
