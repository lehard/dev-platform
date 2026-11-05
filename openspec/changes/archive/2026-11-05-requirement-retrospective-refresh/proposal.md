## Why

A friction event recorded after the Requirement retrospective job, for example during a post-merge fix, blocks terminal reconciliation. The completed retrospective job cannot be re-offered, so the receipt had to be updated by hand.

## What Changes

- `require_checkpoint` distinguishes a checkpoint that is stale only because of later unlinked signals and names them.
- The terminal job records `blocked: retrospective-stale <digest>`.
- `post_merge_progress` offers the retrospective and terminal jobs again under that refresh key, with their own attempt budget.

## Impact

- `template/scripts/{requirement_retrospective,integration_contour,candidate_lifecycle,lifecycle_workers}.py`, docs, tests, manifest.
- Spec: lifecycle-workers.
