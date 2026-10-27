## Why

An operator or session that runs `worktree_cleanup.py cleanup` and reads the exit code is told the cleanup succeeded when it did not: a targeted cleanup with errors reports `"status": "completed"`, and `--all --apply` with errors reports `completed-with-errors` but exits 0, as does a refused `--all` preview. Cleanup is one of the manual post-merge steps the operator repeats; a false success hides a worktree that is still there (BR-771).

## What Changes

- `_cleanup_target`: status `failed` when errors were recorded; `completed` / `already-cleaned` only without errors.
- `main`: exit 1 whenever the cleanup payload has a non-empty `errors` list or status `refused` or `failed` (targeted and `--all`); `scan`, a clean preview and successful cleanups keep exit 0.

## Impact

- `template/scripts/worktree_cleanup.py`.
- Spec: worktree-coordination (one added requirement).
- Tests: `tests/test_worktree_hygiene.py`.
