OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the publication-queue delta, proposal, design and tasks; targeted unit tests through run_test_groups.py --changed-file (7 affected groups, all passing, including test_pr_review_gate, test_queue_archived_readmission, test_publication_queue, test_lifecycle_workers); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (deterministic depth, no ADD): the refusal was located in `_supersession` (`READMISSION_STATES`) and the archived re-open path (`DEVELOPER_FIX_STATES`) before authoring.
- Add the state, keep the guards: `finalize-pending` joins both sets; the same-task, live-claim (`build_job` derives the finalize job) and ancestry checks are unchanged.

## Completeness

- Unclaimed finalize-pending is superseded by a descendant developer handoff and re-enters review with the superseding admission naming `finalize-pending`: `test_developer_handoff_supersedes_the_unclaimed_finalize_job`.
- A merge-only reconcile (unchanged task content) carries the passed review onto the new head: `test_merge_only_reconcile_over_finalize_pending_carries_the_passed_review`.
- Refusals by name, with no comment written: live finalize claim, non-descendant head, another task: `test_finalize_pending_refuses_a_live_claim_an_unrelated_head_and_another_task`.
- Archived change: `local_status` observes and `semantic_readmission` re-opens the handoff for finalize-pending (`WAITING_STATES` in `test_queue_archived_readmission`).

## Correctness

- Existing re-admission behaviour for the other states is unchanged (existing supersession and archived-readmission tests pass unmodified).
- No fallback added: every refusal remains an explicit `QueueError`.

## Coherence

- Spec delta, design and tasks describe the same two-set change; the platform manifest is regenerated.

## Not verified / limits

- Not replayed against the live PR #809 records before merge; the fixture reproduces its state (finalize-pending at the proven head, descendant handoff).
