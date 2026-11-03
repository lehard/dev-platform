## Why

Re-admission after composition repair loses the original queue slot, and repeated advance can run checks while the queue owns the composition. T1 already corrected both platform-lifecycle pre-ready passages; the task-intake/lifecycle-map docs still need to match the post-merge retrospective.

## What Changes

- Order a composition by its first admission; re-admission of that composition keeps the slot.
- Make `execute_requirement advance` fail explicitly, naming the queue state, while the publication queue owns the composition.
- Remove retrospective as a ready/admission/merge condition and align task-intake and lifecycle-map. Preserve the retrospective checkpoint before terminal reconciliation closes the Requirement.

## Success evidence

Re-admission keeps the queue slot; advance on a queue-owned composition fails and starts no checks; both pre-ready spec occurrences allow publication without retrospective; terminal close still refuses a missing checkpoint. All unrelated append-only scenarios remain intact.

## Scope and constraints

Preserve child contribution flow, composition review, finalization, full-check validity (including T1's proven main-only carry) and exact-head required CI. Do not remove or bypass `requirement_terminal.require_checkpoint`. The repair command and main-only implementation belong to the other children.

## Impact

- `template/scripts/{publication_queue,execute_requirement}.py`, tests, generated manifest and docs.
- Specs: platform-lifecycle (one added requirement), publication-queue (added).
