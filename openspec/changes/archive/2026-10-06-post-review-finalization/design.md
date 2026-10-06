## Context
`openspec archive` folds deltas into `openspec/specs`; task-content identity already maps archived paths to active ones and excludes derived spec paths.

## Decisions
1. Finalize job (`post_review_finalization.py`) runs the trusted `openspec_lifecycle.py archive <change> --finalize` in a disposable checkout. The harness first requires the review, selected-checks and semantic-verification gates to be reusable for the exact task-content identity (and the evidence files to match the recorded digests); `--finalize` then reuses review evidence, never launches a review or reruns checks, and skips the local checkout-identity and routing gates that only apply to the developer's task checkout. Only the change's own archive move and spec materialization may change; the harness commits, verifies the task-content identity is unchanged, publishes a `validated-push` receipt (recoverable by `derive_candidate`) and pushes with a lease. A changed identity returns the candidate to review; failures escalate.
2. Admission requires a finalized (archived) change: the queue worker checks the exact PR head tree (`completed_active_changes_at`) before preparing and again before merge, and a completed active change blocks it. `openspec_lifecycle.py check` takes `--stage integration` (strict, used by non-coordinator finish) or `--stage candidate` (a completed managed change is allowed); without a stage only a source-repository work branch or PR is a candidate, so `main` stays strict.
3. Re-derivation: in `_prepare`, when main's changes overlap the candidate only on spec paths of capabilities its archived deltas name, the harness merges main in a disposable clone, takes main's version of those specs, replays the archived delta with the OpenSpec CLI (restoring the candidate's archive byte for byte), runs strict validation, verifies the result is a merge of the claimed head and main that differs from both only on those spec paths with an unchanged task-content identity, and pushes with a lease plus a coordinator `update` marker. Any other overlap still refuses; any failure becomes `integration-repair-pending` (never a block); required checks then run on the result.

## Risks and Mitigations
Replay could mask semantic conflicts: integration checks still run on the actual candidate and strict validation runs after replay.

## Verification
Two-candidate same-spec fixture, semantic conflict fixture, CI rule tests, finalize identity preservation.
