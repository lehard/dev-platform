OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the lifecycle-workers delta, proposal, design and tasks; targeted unit tests (test_autonomous_integration_contour, test_lifecycle_overview, test_lifecycle_workers, test_post_merge_runner, test_pr_review_gate, test_candidate_lifecycle: 368 passing including the new cases); a live read-only discovery against lehard/dev-platform; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Direct handoff (deterministic depth, no ADD). Discovery adds every closed PR labeled `lifecycle:merged` and not `post-merge:settled`, read from a complete paginated listing; the recent window of 50 is kept, so the change only adds candidates.
- `work-next` marks a settled chain (`post_merge_settled`: merged, no next job, no exhausted obligation) through an injected `settle` callback outside the per-PR skip handling; not in `--dry-run`; the overview passes none and stays read-only.
- `work-next --pr N` reads `pulls/N` directly (open always, merged when merged kinds are requested, closed-unmerged never).

## Completeness

- Out-of-window merged PR with an open obligation is a candidate and its job is offered: `test_labeled_merged_pr_outside_the_window_is_a_candidate`, `test_open_obligation_outside_the_window_is_offered`. The overview consumes the same `candidate_prs`.
- Settled marking only for a settled chain, never for open or exhausted ones, not for already-labeled PRs, not in dry run: `test_only_a_settled_chain_is_marked_settled`; a failed label write fails the run: `test_a_failed_settle_label_fails_the_run`.
- Unreadable label listing fails instead of returning a partial set: `test_unreadable_label_listing_fails_instead_of_a_partial_set`.
- Direct `--pr` reads: `test_selected_prs_are_read_directly`, and the CLI test now fakes the direct `pulls/7` read.
- Live read-only check (2026-10-30): `candidate_prs("lehard/dev-platform", include_merged=True)` returned 159 candidates including #678, #681 and #685.

## Correctness

- Every read goes through `_gh_json` / the overview's cached read, which raise on failure; no default or partial substitute.
- Items of the label listing without `pull_request` are Issues, not PR candidates.
- Absence of the settled label is the safe direction: an unlabeled PR is always re-read.

## Coherence

- Spec delta, design, tasks and `docs/engineering/chat-coordinator.md` describe the same bound; the overview's bound note names the label scan; the platform manifest is regenerated.

## Not verified / limits

- The first worker runs after release read the ~110 unsettled `lifecycle:merged` PRs one by one (`pulls/N`) until they are labeled settled; this one-off cost was not measured against the LaunchAgent run bounds.
- `lifecycle_overview.py show --pr N` already read `pulls/N` directly and is unchanged (the Requirement's statement that it could not see an out-of-window PR does not match the code).
