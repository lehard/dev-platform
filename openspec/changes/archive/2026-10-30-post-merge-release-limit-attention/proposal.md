## Why

A failed `work-next --run` releases its claim with a `released:` result; after `MAX_RELEASES` releases a job is no longer claimable (`is_claimable`). For pre-merge kinds the worker then publishes `blocked-escalation`. For post-merge kinds (retrospective, terminal reconciliation, cleanup) nothing happens: the PR is already merged, released results never count as obligation attempts, so derivation keeps naming the same job as `next_job` while no worker may claim it. The obligation silently stops (BR-767 tail; BR-925 noted it as a limit).

## What Changes

- Derivation: when the next post-merge job of a merged candidate has `MAX_RELEASES` trusted released results, the candidate offers no job and the obligation counts as exhausted (`post_merge_exhausted`), with reason `post-merge <kind> exhausted N claim releases of attempt A (last: <cause>); operator action required` and `post_merge_released` detail.
- Worker: the run whose release reaches the limit for a post-merge kind calls the existing `ensure_post_merge_attention` (a failed attention post fails the run naming both causes); it never publishes `blocked-escalation` for a merged PR.
- Because the state is an ordinary exhausted obligation, the lifecycle overview finding and `reoffer-post-merge` (BR-925) apply unchanged; a re-offer gets fresh job ids and so a fresh release budget. The permitted-action text names the release count and last cause.

## Impact

- `template/scripts/candidate_lifecycle.py`, `template/scripts/lifecycle_workers.py`, `template/scripts/pr_review_gate.py`, tests, platform manifest.
- Specs: lifecycle-workers (added requirement).
- Pre-merge release escalation unchanged.
