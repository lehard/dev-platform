OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the lifecycle-workers, publication-queue and chat-coordinator deltas, proposal, design and tasks; targeted unit tests (test_post_merge_runner, test_autonomous_integration_contour, test_lifecycle_overview, test_pr_review_gate, test_candidate_lifecycle, test_lifecycle_workers, test_requirement_contribution_composition: 414 existing plus the new cases passing); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (deterministic depth, no ADD): the Requirement names the mechanics; pacing lives in the runner (per-round `--exclude-pr`), not in the pure derivation.
- The re-offer is an appended coordinator record at the merged head (state `merged`, `post-merge-reoffers` sequence, event in `next_job`), reusing the existing `:r{seq}` job-id suffix; `job_record` now accepts a re-offer for post-merge kinds.
- One eligibility function (`pr_review_gate.post_merge_reoffer_plan`) serves the command, the overview and the attention comment.

## Completeness

- At most one attempt per obligation per round, other PRs still served, exclusion lasting one round: `test_blocked_obligation_waits_for_the_next_round_while_other_prs_are_served`, `test_an_excluded_pr_is_neither_read_nor_offered`.
- Environment defect: missing `lsof` fails the round before any `work-next` call (`test_missing_process_check_tool_fails_before_any_claim`); `process-check-unavailable` after claim raises `PostMergeEnvironmentError` with no receipt posted (`test_an_unavailable_process_check_fails_the_run_without_a_receipt`); `work-next` releases the claim and exits 2 through its existing `WorkerError` path.
- Re-offer: fresh budget under `:r1`, completed retrospective/terminal not re-offered, `already-clean` completes, second exhaustion re-offerable as `:r2`, refusals for another head, empty head/reason, live claim, open PR and nothing exhausted with no write, malformed sequence without event, CLI wiring and attention text naming the command and last outcome: `PostMergeReofferTests`.
- `already-clean` when no worktree of the branch exists: existing `test_no_local_worktree_is_already_clean` and `test_cleanup_reports_removed_clean_and_refused_states`, plus the re-offer test above.
- Overview lists `reoffer-post-merge` with the merged head and the last outcome: `test_exhausted_post_merge_obligation`.

## Correctness

- Derivation without a re-offer is unchanged (same ids, same exhaustion reason); existing post-merge derivation and composition tests pass unmodified. One existing assertion that a post-merge retrospective rejects a re-offer event was replaced by the new contract (post-merge kinds accept it; integration-repair still rejects).
- `active-board`, dirty, mismatch and foreign-commit refusals stay `blocked` outcomes; only `process-check-unavailable` is classified as environment.
- No default substitutes: missing `--expected-head`, reason, actor, record or event fail explicitly.

## Coherence

- Spec deltas, design, tasks, `docs/engineering/chat-coordinator.md` and `docs/engineering/hosted-lifecycle-workers.md` describe the same flow; the platform manifest is regenerated.

## Not verified / limits

- Not exercised against live GitHub or the installed LaunchAgent; the six stuck PRs are re-offered after merge with the new command.
- A post-merge job whose claim is released `MAX_RELEASES` times (repeated environment failures) is no longer claimable until re-offered; the runner precheck prevents the known case, and the overview does not yet name that state.
