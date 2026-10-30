OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the lifecycle-workers delta, proposal, design and tasks; targeted unit tests (test_autonomous_integration_contour, test_lifecycle_overview, test_lifecycle_workers, test_pr_review_gate, test_candidate_lifecycle, test_requirement_contribution_composition, test_post_merge_runner: 434 passing including the new cases); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Direct handoff (deterministic depth, no ADD). A post-merge job released `MAX_RELEASES` times is derived as an exhausted obligation (`post_merge_exhausted`, release-specific reason, `post_merge_released` detail), so the existing attention, overview finding and `reoffer-post-merge` apply without a new state or path.
- The worker run whose release reaches the limit posts `ensure_post_merge_attention`; a failed post raises `WorkerError` naming both causes. Pre-merge kinds keep `blocked-escalation`.

## Completeness

- Offered below the limit; exhausted with count and last cause at the limit; `post_merge_job` agrees: `test_job_is_offered_until_the_release_limit_then_counts_as_exhausted`.
- Attention body and permitted action name the releases, last cause and the `reoffer-post-merge` command: `test_attention_names_the_releases_and_the_reoffer_command`.
- Re-offer restores a job under `:r1` with no releases counted: `test_reoffer_gives_a_released_job_a_fresh_budget`.
- Third release of a post-merge run posts the attention once and publishes no `blocked-escalation`: `test_third_release_of_a_post_merge_run_posts_the_attention`; pre-merge escalation: existing `test_cli_run_failure_releases_the_claim_and_escalates_after_the_bound` unchanged and passing.

## Correctness

- Releases are counted for the exact offered job id (kind, head, attempt, re-offer sequence) from trusted results only, the same counting `is_claimable` uses, so derivation and claimability agree.
- The reason keeps the `post-merge <kind> exhausted` shape matched by the attention and overview.

## Coherence

- Spec delta, design and tasks describe the same behavior; the platform manifest is regenerated.

## Not verified / limits

- Not exercised against live GitHub. `IntegrationRepairBoundTests::test_bound_blocks_the_candidate_after_two_attempts_and_the_next_one_still_merges` failed once in a loaded combined run and passed alone (git-heavy test under machine load; untouched code path).
