# Verification: early shared Requirement PR

OpenSpec-Verify: PASS
Verification-Method: Manual scenario-by-scenario review of the agent-workflow and platform-lifecycle delta specs against the implementation in requirement_integration.py, execute_requirement.py, project_publish.py and publication_state.py and the new regression tests; full platform check suite; independent review.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Scenario coverage:

- Draft PR opens before all children finish and later children append to the same PR: `test_early_candidate_grows_by_fast_forward_on_the_same_branch` (real git: one-child candidate, main advances, second child appended on the same branch as a fast-forward, history is child/bind/child/bind), `test_advance_opens_shared_draft_after_first_ready_child_then_starts_next` (supervisor opens the draft with `expected_changes`, then starts the next child, no retrospective yet), `test_appended_head_reuses_the_existing_pr_without_fresh_base_or_duplicate` (stale-head PR is re-observed after push; no second PR).
- Incomplete candidate cannot be readied, merged, queued or reconciled Done: `test_incomplete_shared_candidate_publishes_draft_without_ready_or_merge`, `test_incomplete_shared_candidate_puts_a_ready_pr_back_to_draft`, `test_incomplete_publication_is_draft_only_and_skips_full_checks`, `test_merged_incomplete_candidate_is_never_reconciled_terminal` (names the missing change). The complete candidate marks the same draft ready before the unchanged protected merge: `test_complete_shared_candidate_marks_the_same_draft_ready_before_merge`.
- Divergent or reordered growth refused: `test_diverged_candidate_history_blocks_append`, `test_early_candidate_rejects_out_of_order_or_single_expected_change`.
- Interrupted rerun resumes: compose returns `resumed` for an identical candidate; `_existing_candidate` finds the single matching branch and reuses its recorded base (`test_existing_early_candidate_keeps_its_recorded_base`); more than one match blocks.
- Legacy one-shot candidates and single-child Requirements are unchanged: the pre-existing 27 integration, execution and end-to-end tests pass without behavior edits.

Checks:

- `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 scripts/run_test_groups.py --all` (15 groups) and `python3 template/scripts/openspec_lifecycle.py check` all passed. A later wording-only change (naming the missing changes in the refusal messages) was verified with the focused test modules (38 tests) and the changed test, not by a second full run before archive.

Not exercised / residual risk:

- No live GitHub run: `gh pr create --draft`, `gh pr ready` and `gh pr ready --undo` are covered only through mocks, not against a real repository PR.
- The draft state is the native merge barrier. A person who manually marks an incomplete candidate ready on GitHub is not blocked by a CI check; the platform's own terminal reconciliation refuses it, and the publisher puts such a PR back to draft on the next run.
- Release and managed rollout are post-merge operational steps with the existing release path and are not part of this change's verification.
