## Why

Finalization publishes a `contribution-integration` job bound to the requirement branch head it observed (`target_head`). When another contribution integrates first, that branch fast-forwards and `merge_reviewed_contribution` returns `discarded` for the stale job, both when the head differs from the job's `target_head` and when the branch moves during the run. Nothing offers a new job, so the reviewed contribution stays in `contribution-integration-pending` until an operator re-publishes the job by hand. This is the missing supported re-base of a contribution onto the new requirement branch head.

## What Changes

- `template/scripts/requirement_contributions.py`: when the observed requirement branch head differs from the job's `target_head`, or the branch moves before the merge, the worker checks that the moved head still contains the contribution base and re-offers the same `contribution-integration` job for the same candidate head bound to the moved head (`adapter.publish_job`, existing API), returning `target-moved`. A moved head without the base raises `ContributionError` naming it. A lost claim still discards without publishing.
- Tests: re-offer on a moved head, refusal when the base is gone, no re-offer on a lost claim, unchanged merge when the head matches.

## Impact

- `template/scripts/requirement_contributions.py`, tests, platform manifest.
- Spec: platform-lifecycle (one added requirement).
- No change to `publication_queue.py` or job identity: the re-offered job differs from the stale one only by its `target_head`, which is already part of the job id.
