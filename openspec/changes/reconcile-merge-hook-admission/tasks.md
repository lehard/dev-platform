## 1. Hook and reconcile

- [x] 1.1 `pre-merge-commit`: admit a merge only in a linked task worktree with a matching one-shot intent (branch, `GIT_REFLOG_ACTION`, `origin/<main>` commit) and consume it; integration copy always blocked; message names reconcile instead of rebase.
- [x] 1.2 `task_reconciliation.py`: write the intent before its merge and remove it after, whatever the outcome.
- [x] 1.3 `blocking-gates.toml`: resolve and correct known gap 3, drop the hook caveat from task-freshness recovery, register the new tests.

## 2. Verification

- [x] 2.1 Regression tests: reconcile with the installed hook passes (and fails without the fix, #420); merge without intent, another ref, another worktree, stale intent and integration copy are rejected; no intent remains.
- [ ] 2.2 Run full validation, the public distribution snapshot smoke and semantic OpenSpec verification; record the downstream verification limits.
