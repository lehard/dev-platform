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

- [x] 4.4 Make the friction-window fixtures in `tests/test_autonomous_integration_contour.py` relative to the run time: fixed 2026-10-0x dates fell out of the 14-day `AMBIGUOUS_WINDOW_DAYS` on 2026-10-17 and failed the mandatory suite on main independently of this change.

- [x] 4.5 Disable detached Git auto-maintenance in `tests/upgrade_smoke.py`: on the CI runner (Git 2.55) it wrote into the temporary project's `.git` during cleanup and failed the upgrade smoke after it had passed (Errno 39), on three consecutive runs of this candidate.

## 5. Verification and delivery

- [x] 5.1 Regenerate the platform manifest; required platform checks; truthful semantic verification; archive; retrospectives; publication.
