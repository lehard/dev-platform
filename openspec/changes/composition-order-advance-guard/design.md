## Decisions

- **First admission key.** The composition ordering key is derived from the first immutable admission on the same PR and exact Requirement composition branch, including admissions before a block. The current admission remains authoritative for gates and head; only the sort key is preserved. Other candidates retain current ordering.
- **Explicit refusal.** While the queue owns the composition (queued, preparing, integrating or repairing), advance first queries the exact shared-branch PR and refuses on a live queue label or coordinator-owned lifecycle state, naming the state and owner before checks, child materialization or publication; unreadable or ambiguous observations fail explicitly.
- **Both pre-ready occurrences.** T1 already carries the identical requirements and all their scenarios; this change does not duplicate them.
- **Terminal checkpoint stays.** Remove retrospective only from ready, admission and merge preconditions. Keep all final gates for terminal reconciliation and explicitly require its retrospective checkpoint; `requirement_terminal.require_checkpoint` stays unchanged.
- **Portable shared publication.** Without coordinator queue ownership, advance publishes the completed shared candidate without a retrospective checkpoint; after delivery it still requires the checkpoint before terminal reconciliation. A disabled queue cannot own a candidate; when enabled, an empty successful PR inventory proves there is no open candidate to own.
- **Aligned docs.** Correct the joint-composition passage of task-intake and the stale pre-merge composition retrospective in lifecycle-map. Preserve the existing portable lifecycle and post-merge job ownership.

## Dependency and verification

T3 still depends on T1's composition gate behavior. This delta permits proof-bound main-only full-check carry while keeping exact-head required CI before ready. Verify stable re-admission ordering, no checks on refused advance, both corrected pre-ready scenarios, preservation of every unrelated append-only scenario, and terminal-close rejection without the checkpoint. No queue state or receipts are edited by hand.
