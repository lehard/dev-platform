# Verification: Scope deferred worktree cleanup

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal/design/delta spec plus focused safety regression and full platform test suite
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The ordinary cleanup API and CLI now require the exact deferred
  `worktree`/`branch`/`head` tuple.  It selects only a matching record, keeps
  every non-selected record intact, and returns `already-cleaned` for a stale
  target rather than resolving a replacement path.
- Deferred recovery preserves the existing managed-directory, process, board,
  Git worktree identity, branch/head, lock/prunable, and cleanliness gates.
  The target path is normalized to an absolute path before matching.
- Global cleanup is explicit and two-step: `cleanup --all` returns a bounded
  preview (maximum 50 candidates); only `cleanup --all --apply` mutates all
  independently safe candidates.  Deferred-record paths are protected from
  the generic old-worktree pass, so a stale or ambiguous record fails closed
  rather than being reinterpreted as an ordinary cleanup candidate.
- `finish_task.py` records and prints the exact targeted recovery command.
  The implementation contains no reset, stash, or Git-clean operation; a
  targeted execution uses only the exact selected record's worktree/branch.

## Executed evidence

- `python3 -m unittest -v tests/test_worktree_hygiene.py` — PASS (31 tests).
  `test_targeted_cleanup_cannot_remove_another_deferred_worktree` creates two
  real deferred Git worktrees, physically removes only the selected first
  worktree, asserts that the second worktree still exists, and asserts that
  its exact deferred record remains unchanged.  It also proves that a stale
  target does not remove a replacement identity.
- `python3 -m unittest -v tests.test_worktree_hygiene.DeferredCompletedWorktreeCleanupTests` — PASS (6 tests), including bare-default refusal, explicit global preview/apply, stale/mismatched identity, and ambiguous-record failure.
- `python3 scripts/worktree_cleanup.py cleanup` — refused with a required
  exact target or `--all`, before any mutation.
- `python3 scripts/worktree_cleanup.py cleanup --all` — PASS; preview only,
  with zero candidates and one independently blocked active deferred record.
- `python3 scripts/run_test_groups.py --all` — PASS; 727 declared/discovered
  tests across 13 groups, no failed groups.
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS.
- `openspec validate scope-deferred-worktree-cleanup --strict` — PASS.
- `python3 template/scripts/openspec_lifecycle.py check` — PASS before archive.
- `git diff --check` — PASS.

## Coherence

The code, central/template guidance, tests, and completion-lifecycle delta all
express task-scoped deferred cleanup as the default and reserve global cleanup
for explicit, reviewed `--all --apply`.  No material divergence remains.
