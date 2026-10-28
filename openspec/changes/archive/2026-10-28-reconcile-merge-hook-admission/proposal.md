## Why

Task reconcile incorporates current authoritative main by a normal merge, never a rebase, so that a published PR is updated by fast-forward push on the same branch. Where doctor installed the platform `pre-merge-commit` hook (downstream multi-agent projects), the hook rejects every merge commit in a task worktree and asks for a rebase or a manual `DEV_PLATFORM_ALLOW_MERGE_COMMIT=1`. Reconcile therefore cannot update a published PR without manual intervention (lehard/dev-platform#420, #403, #408), and agents fell back to GitHub update-branch, which breaks PR identity. The central repository does not install the hook, so its own dogfood reconcile never showed the defect.

## What Changes

- Before its single `git merge --no-edit origin/<main_branch>`, reconcile writes a one-shot intent into the task worktree's own git directory (`$(git rev-parse --git-dir)/dev-platform-reconcile-merge`) naming the task branch and the commit `origin/<main_branch>` points to, and removes it after the merge whatever the outcome.
- `pre-merge-commit` admits a merge commit only when, at the same time, it runs in a linked task worktree, that worktree's git directory holds the intent, the intent names the current branch, `GIT_REFLOG_ACTION` is exactly `merge origin/<main_branch>`, and `origin/<main_branch>` still points to the recorded commit. It consumes the intent. Every other merge commit stays blocked: no intent, another ref, another worktree, a stale intent, the integration copy. The hook is not removed; `DEV_PLATFORM_ALLOW_MERGE_COMMIT` remains the only manual override.
- `blocking-gates.toml`: known gap 3 is resolved and corrected (committing a resolved reconcile conflict uses `git commit`, which does not run `pre-merge-commit`); the task-freshness recovery no longer tells agents to stop at the hook.
- Regression tests reproduce #420 with the real hook installed and prove the admission is bounded.

## Impact

- `template/scripts/git_hooks/pre-merge-commit`, `template/scripts/task_reconciliation.py`, `template/dev-platform/blocking-gates.toml`.
- Tests: `tests/test_task_reconciliation.py`, `tests/test_blocking_gates.py`.
- Downstream projects receive the hook through doctor after a platform release.
