OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle delta, proposal, design and tasks; new and updated unit tests; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- `finish_task.sync_queue_merged_task` runs before the managed-candidate handoff branch. When the exact queue PR is merged, it synchronizes the worktree to the proven merged head and finish skips the handoff. The existing merged reconcile then takes over, before the consolidated preflight, so no board scope claim is required.
- An unreadable queue status (`Publication queue observation blocked`) or a failed synchronization (`Merged PR task synchronization blocked`) stops finish explicitly.

## Completeness

- `tests/test_finish_merged_queue.py`:
  - a managed candidate whose exact queue PR is merged synchronizes to it and reconciles, with no developer handoff and no preflight;
  - an open candidate still hands off;
  - the admission tests account for the new first observation.
- Spec scenario "Merged PR at a pre-finalize head": covered by the merged-candidate test.

## Not verified / limits

- No live post-merge finish was run; `#960` is the live acceptance case, after the sibling terminal child.
- `task_pr_is_already_merged` returns False when GitHub CLI authentication is unavailable; that existing behaviour is unchanged (reported, not touched).
