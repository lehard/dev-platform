## Why

Archive gates raise at the first failure, so a candidate that misses several preconditions needs one archive run per missing item (three runs in a row in a recorded friction), and archive itself may launch an independent review, spending review outside the review job.

## What Changes

- `openspec_lifecycle.finalize_change(root, change, *, context)`: collects every unmet precondition (tasks and Purpose, verification receipt, review evidence, routing evidence, automated-check evidence, committed package, private lineage, checkout identity) into one error listing each with its fix, then validates, rehearses and archives with recovery.
- Archive requires review evidence only; `ensure_review_evidence` is no longer called from archive.
- `post_review_finalization.trusted_archiver` archives through `finalize_change`.

## Impact

- `template/scripts/{openspec_lifecycle,post_review_finalization,independent_review}.py`, tests, manifest.
- Spec: completion-lifecycle (one requirement modified, two added).
