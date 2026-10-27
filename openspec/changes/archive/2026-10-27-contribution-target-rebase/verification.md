OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the contribution-target-rebase platform-lifecycle delta, proposal, design and tasks; targeted unit tests on Python 3.13 and 3.11 with real bare-remote git fixtures and a stubbed queue adapter; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Owner decisions

- BR-771 fifth and last slice, scoped by the coordinator on 2026-10-27 with technical choices delegated: supported re-base of a contribution onto a moved requirement branch head. The coordinator asked to be told first if the slice touched `publication_queue.py`, readmission or the finish path (parallel BR-837); it does not.

## Implementation

- `template/scripts/requirement_contributions.py`: `_reoffer_on_moved_target(root, repo, candidate, checkout, moved_head, *, adapter, claim_current)` requires `merge-base --is-ancestor <contribution_base> <moved_head>` (a failure raises `ContributionError` naming the moved head, the base and the git error), then, only while the claim is current, calls the existing `adapter.publish_job(..., "contribution-integration", candidate head, task_identity=identity, target_head=moved_head)` and returns `{"state": "target-moved", "number", "target_head"}`; a lost claim returns `discarded` and publishes nothing. `merge_reviewed_contribution` uses it at both points that returned `discarded` for a moved branch: the checked-out target head differs from the job's `target_head`, and `ls-remote` shows the branch moved before the protected merge (the moved head is fetched first). The contribution is never merged in a run whose job is bound to another head.
- No change to `publication_queue.py`, `lifecycle_workers.py` or finalization. The re-offered job differs from the stale one only by `target_head`, which `job_id` already includes; the worker posts `target-moved` as the stale job's result.

## Completeness

- Another contribution integrated first: `test_moved_target_reoffers_the_job_on_the_new_head` (exact `publish_job` call, no merge API call, no transition, remote branch unchanged).
- Branch moves during the run: `test_target_moving_during_the_run_reoffers_on_the_observed_head` (the branch is advanced from inside the conflict check; re-offer bound to that head, no merge).
- Base no longer contained: `test_moved_target_without_the_contribution_base_fails_without_reoffer`.
- Lost claim: `test_moved_target_with_a_lost_claim_publishes_nothing`.
- Matching head: `test_matching_target_head_merges_without_reoffer` (protected merge, manifest append, `contribution-integrated`, no re-offer).

All tasks in `tasks.md` are complete; 2.2 is this receipt together with the regenerated platform manifest and the selected checks.

## Correctness and coherence

- `tests/test_requirement_contribution_composition.py` (62) and `tests/test_shared_writer_guard.py` pass on 3.13; `test_requirement_contribution_composition` passes under Python 3.11; `compileall` under 3.11 and `ruff` clean.
- A first version of the rewritten-history fixture was flaky: a manifest commit recreated from the same base within the same second was byte-identical to the boundary, so the "rewritten" head still contained the base. The fixture now commits a distinct file first; 40 repeated runs of that case and 5 runs of the group passed.
- Limitation: the queue adapter is stubbed; the GitHub merge API is simulated by a local merge and push.
