OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the terminal-reconcile-fresh-main agent-workflow delta, proposal, design and tasks; targeted unit tests on Python 3.13 and 3.11 run during the change, including a mutation check of the regression test; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-771 third slice, scoped by the coordinator on 2026-10-27 with technical choices delegated: terminal reconcile on a fresh origin/main without a manual fast-forward, plus a regression test for post-merge finish without a claim. Abandoned unmerged worktrees and contribution re-base stay remainder.

## Implementation

- `template/scripts/managed_task.py`: `CommittedLineage` and `resolve_committed_lineage(root, commit, *, source_issue, change)`. It lists `openspec/changes` of the commit with `git ls-tree -r`, takes the canonical active (`changes/<change>`) and archived (`archive/*-<change>`, legacy `archive/*/<change>`) directories that commit `.managed-task.json`, materializes only those provenance files into a temporary directory and validates each with the existing `_provenance_for` against `root` (private lineage handles are authorized as before). `verified` is whether the commit has `verification.md` in that directory. A lineage of another source or more than one match raises `ManagedTaskError`; no lineage returns `None`. The checkout is not read or changed.
- `template/scripts/requirement_terminal.py`: `reconcile_parent` calls `managed_task.target_main(root)` (fetch `origin/<main_branch>`, failure raises) once after the retrospective gate, and requires each child's lineage in that commit to be archived and verified; the refusal names the child and the commit. The integration-main branch precondition is unchanged.
- `template/scripts/execute_requirement.py`: `_done_child_is_delivered` uses the same fetched-commit proof.
- Post-merge finish without a claim needed no code change: a queue-merged task reaches `reconcile_confirmed_remote_pr_merge` before `observe_completion_blockers`, the only scope-gate call on that path, and `finish_board` is a no-op without a claim.

## Completeness

- Integration main was not fast-forwarded: `test_archive_merged_only_on_origin_main_proves_delivery_without_moving_local_main` (real bare remote and clones; local HEAD, status and working tree unchanged after reconciliation).
- Remote main lacks the archive: `test_archive_only_in_the_local_checkout_does_not_prove_delivery`, `test_archive_without_verification_receipt_on_origin_main_is_refused`.
- Target lacks a terminal path (unchanged scenario): existing `test_terminal_reconciliation_refuses_unsupported_target_before_parent_mutation` and `test_terminal_reconciliation_checks_parent_before_mutation` pass.
- Resolver semantics: `test_committed_lineage_of_another_source_fails_closed`, `test_committed_lineage_reports_archived_verified_location`; Done-child check: `test_done_child_check_reads_origin_main`.
- Claimless post-merge finish: `test_post_merge_finish_completes_without_a_board_claim` drives `finish_task.main` with a real board that has no claim for the worktree and a required scope gate; it asserts exit 0, no evidence regating, parent reconciliation called, no `agent_board.py finish` spawned and an unchanged board, and that the same board fails `enforce_scope_gate`. Mutation check: inserting `enforce_scope_gate` before the queue-merged branch makes the test fail.

All tasks in `tasks.md` are complete; 2.3 is this receipt together with the regenerated platform manifest and the selected checks.

## Correctness and coherence

- Targeted: `tests/test_requirement_terminal_fresh_main.py`, `tests/test_finish_merged_queue.py`, `tests/test_requirement_retrospective.py` under Python 3.11 (`unittest`, 21 tests OK) and 3.13; `tests/test_requirement_execution.py`, `test_managed_status_lifecycle.py`, `test_requirement_flow_e2e.py`, `test_requirement_integration.py`, `test_autonomous_integration_contour.py` (187 tests) pass. `compileall` under 3.11 OK.
- Design coherence: only remote-tracking refs move (fetch); no fast-forward, switch or worktree of the integration checkout, consistent with the rule that only post-merge finish advances integration main.
- New test module registered in `dev-platform/checks.toml` group `fast-f`.
- The first full run failed only `test_shared_writer_guard.test_new_direct_writers_require_review`: the new temporary-directory `write_text` in `resolve_committed_lineage` was not in the reviewed writer baseline. It writes only a git-object copy into a private `tempfile.TemporaryDirectory`, so it was added to `REVIEWED_BASELINE` with that reason; the recorded selected checks are the rerun on that head.
- Limitation: GitHub Issue/Project state is stubbed in the tests; the git side is real.
