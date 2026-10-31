## Context

`_worker_candidate` integrates a blocked-retryable candidate with no red gate (`red_retry_blocks_integration` is False, the state is not in `NOT_INTEGRABLE`, not `review_owned`). `_prepare` detects a conflict with `merge_conflicts` (`git merge-tree`):
- a conflict outside derived and generated paths raises `IntegrationRepairNeeded`, and `_integrate` routes it to `_integration_repair`, which counts the attempt;
- a conflict only in declared generated or derived paths takes `prepare_derived_specs`;
- `RederivationEnvironmentFailed` becomes `QueueEnvironmentError`, and `_integrate` only releases the active label and re-raises.
`candidate_lifecycle.derive_candidate` reads v2 records and v1 events, and a pending exact-head check state sets the reason "required checks not yet reported".

## Decisions

- **Note.** `_note_environment_error(root, repo, number, head, detail)` posts a v1 event `{"kind": "environment-error", "head", "reason"}` through `_comment`. It skips the post only while the derived candidate already shows that reason for the head (a later record supersedes a note, so a recurrence is posted again), and it raises `QueueError` when the head is unavailable. `_integrate` calls it in its `QueueEnvironmentError` handler before re-raising; a failed note raises `QueueEnvironmentError` naming both failures.
- **Derivation.** `derive_candidate` remembers the position of the last environment-error event for the current head. The reason text comes from that same head's note (`environment_reason`). If that event is newer than the latest exact-head v2 record and the state is ready, integrating or blocked-retryable, the reason becomes "coordinator environment error on this head: <reason>". Nothing else changes. The v1-only fallback ignores environment-error events, so the note never stands in for an admission or a block.
- **No mergeability.** The conflict signal stays `merge-tree` in `_prepare`. GitHub `mergeable` is not read.

## Risks

- A note persists as the reason until a later record for the head is written. A fixed environment is followed by a new integration record, which supersedes it.
