# Verification: Stabilize dogfood validation failure signals

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active proposal, design and delta specifications against the implementation and focused regression tests, followed by the authoritative full test-group run.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The reconciliation-lock regression replaces a fixed startup sleep with an
  explicit ready signal. Its outer process deadline is bounded but tolerant of
  concurrent scheduling, while a separate ready-but-hung lock holder still
  proves deterministic lifecycle timeout behavior.
- The Codex help probe retains its 30-second bounded contention-tolerant
  deadline and now has regression coverage for both the configured deadline
  and a genuine timeout without retry.
- Terminal merge/reconciliation still happens before cleanup. When the caller
  occupies the completed worktree, cleanup records the exact path, branch and
  head instead of deleting that cwd. Recovery only removes an inactive,
  board-free, clean and identity-matched worktree/branch, and repeated recovery
  is idempotent. The existing failure-path tests continue to prove that failed
  merge/reconciliation does not reach cleanup.
- A mature project can retain its project-owned legacy `worktree_cleanup.py`.
  The optional deferred-cleanup import therefore treats a missing helper symbol
  as compatibility fallback rather than making normal project-harness startup
  fail.

## Automated evidence

- `python3 -m unittest -v tests.test_worktree_hygiene.DeferredCompletedWorktreeCleanupTests tests.test_pr_reconciliation_concurrency.ReconciliationLockTests tests.test_delegated_write_guard.CodexTierTests`
- `python3 -m unittest -v tests.test_git_lifecycle.GitLifecycleTests.test_multi_agent_pr_finish_reconciles_remote_merge_after_nonzero_gh_exit tests.test_managed_status_lifecycle.ManagedStatusLifecycleTests`
- `python3 tests/project_harness_adoption_smoke.py`
- `python3 scripts/run_test_groups.py --all` — PASS: 605 discovered/declared tests, 13 groups, `failed_groups: []`.
- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `openspec validate stabilize-dogfood-validation-failure-signals --strict`
- `python3 template/scripts/openspec_lifecycle.py check`
