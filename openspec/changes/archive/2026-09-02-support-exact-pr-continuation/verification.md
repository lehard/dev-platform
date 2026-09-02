# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) against proposal/design/delta spec plus the full local platform test and validation matrix
Automated-Checks-Evidence: automated-checks.json

## Automated validation

Run locally on branch `agent/support-exact-pr-continuation`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — OK, 831/831 across 13 groups (see automated-checks.json)
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate support-exact-pr-continuation --strict` — valid
- `python3 scripts/select_checks.py --base origin/main` — `high-impact-path`, selection `ready`
  (the executable-surface change maps to the protected full suite, not a bounded subset)

Targeted suites re-run directly: `test_task_reconciliation.py` (11),
`test_publication_recovery_cli.py` (17), `test_project_terminal_reconciliation.py`,
`test_pr_reconciliation_concurrency.py`, `test_publication_state.py` (28),
`test_merge_lifecycle_resilience.py` (4) — all pass.

New regression coverage in `tests/test_task_reconciliation.py`:

- `test_issue_97_local_ci_fix_descendant_continues_same_exact_pr_after_main_advance`
  — a local CI-fix commit on top of an already-published exact open PR head, with
  authoritative main advanced, is reconciled by fast-forwarding the same remote
  task branch to the descendant and then to the merged head; PR identity is
  re-proven, `origin/agent/task` equals the reconciled `HEAD`, and that head
  contains the published head, the CI fix and `origin/main`.
- `test_issue_97_squash_merged_exact_pr_routes_to_terminal_finish_without_new_head`
  — when GitHub proves the exact task head already `MERGED` (remote branch
  deleted), reconcile refuses with a message pointing at `finish_task.py` for
  terminal local reconciliation and creates no merge commit (`HEAD` unchanged, no
  `MERGE_HEAD`).
- `test_issue_97_diverged_local_head_is_still_refused` — a remote task branch that
  gained a commit the local head does not contain, plus a divergent local commit,
  keeps the strict "remote task branch head differs" refusal with no mutation.

Existing `test_remote_branch_with_changed_head_is_refused_before_merge` and
`test_issue_190_open_exact_pr_is_reconciled_and_remains_fast_forward_pushable`
still pass unchanged.

## Semantic review

Completeness: PASS.

- Delta requirement "An exact open PR may continue from a proven local descendant"
  — `reconcile()` now routes the `published and remote_branch_head != local_head`
  case through `_continue_exact_pr_from_local_descendant`, which proves
  `relation(remote_branch_head, local_head) == "behind"` (remote head is a strict
  ancestor), re-proves the exact open PR at the unchanged remote head via
  `_require_exact_open_pr(..., proof_head=remote_branch_head)`, performs a
  non-force `git push origin <local_head>:refs/heads/<branch>`, re-reads the
  remote head, and re-proves PR identity at the new head before the normal
  `origin/main` merge and existing fast-forward push/validation continue. Scenario
  "Remote identity or history changed" — non-`behind` ancestry, a changed PR head
  (`stale_open`), a base that no longer targets main, an unreadable/foreign head
  owner, or a non-fast-forward push each raise `SystemExit` with no force, rebase
  or guessed recovery.
- Delta requirement "Exact merged PR recovery is terminal" — `_require_exact_merged_is_terminal`
  runs before `observe()`/merge and, whenever GitHub proves an exact `MERGED` PR
  for the branch head (even with the remote branch already deleted), stops
  reconcile and directs the operator to `scripts/finish_task.py`. The existing
  `finish_task.py` recovery order (`task_pr_is_already_merged` →
  `reconcile_confirmed_remote_pr_merge`) then synchronizes authoritative local
  main and managed status without creating, updating or publishing another task
  head or PR; the guard's contribution is preventing reconcile from producing a
  fresh merge head that would defeat that exact-head detection.

Correctness: PASS.

- `_require_exact_open_pr` is unchanged except that its head parameter is named
  `proof_head` and threaded through; all four identity checks (available,
  `stale_open`, `exact_merged`, base branch, head-repository owner) still apply,
  now against whichever head the caller must prove.
- The continuation push targets an explicit SHA and `refs/heads/<branch>` without
  `--force`/`--force-with-lease`, so a concurrent remote change makes the push
  non-fast-forward and Git itself rejects it; the subsequent `_remote_branch_head`
  re-read and second `_require_exact_open_pr` close the observe/act gap.
- `_require_exact_merged_is_terminal` returns silently only when GitHub auth is
  absent, which already blocks `publish_mode=pr` finish at
  `validate_publication_config`, so no republish can follow that path.
- Post-merge, the pre-existing published block re-reads the remote head, re-proves
  the exact open PR and fast-forward pushes the reconciled head; the continuation
  leaves `remote_branch_head == local_head` so that block behaves exactly as for
  the unchanged-head case.
- When authoritative main has not advanced, a continuation still fast-forwards the
  PR branch and then returns at the existing no-op guard — the CI fix reaches the
  PR without a spurious merge commit.

Coherence: PASS. The change is confined to `template/scripts/task_reconciliation.py`
and its tests. It reuses `publication_state` (`find_exact_head_pr`,
`find_exact_local_branch_pr`, `ExactHeadPrLookup`), the existing
`task_reconciliation` merge/observe/push flow, and the existing
`finish_task.py` terminal path (`project_terminal_reconciliation` semantics via
`reconcile_confirmed_remote_pr_merge`). No new publication state machine, no
rebase, no force-push, and no second delivery backlog were introduced, matching
the accepted boundaries in `proposal.md` and `design.md`.

## Scope boundary

Force-push, rebase, a new PR for an already merged delivery, and acceptance of
ambiguous remote history remain out of scope and unimplemented.
`harness_mode=project` consumers are unaffected (the helper is gated on
`harness_mode=platform`, `publish_mode=pr`).
