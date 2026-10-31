OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the publication-queue delta, proposal, design and tasks; new and updated unit tests; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- On 2026-11-01 the coordinator narrowed BR-969 item 2 (variant A). The conflict path already exists: `_prepare` detects conflicts through `merge-tree`, a real conflict becomes counted integration repair, and a generated-only conflict takes the derived merge. GitHub mergeability is not read.
- `publication_queue._note_environment_error` posts a v1 `environment-error` event with the exact head and failure. It skips a repeat of the same head and reason, and raises when the head is unavailable. `_integrate` calls it in the `QueueEnvironmentError` handler, after releasing the active label and before re-raising. It records no transition, block or job.
- `candidate_lifecycle.derive_candidate` remembers the last environment-error event for the current head. When that event is newer than the latest exact-head v2 record and the state is ready, integrating or blocked-retryable, the reason becomes "coordinator environment error on this head: …". State, gates and attempts are unchanged. The v1-only fallback ignores these events.

## Completeness

- `tests/test_publication_queue.py`:
  - `_integrate` on an environment error records no transition, job or block and calls the note once with the exact head;
  - the note posts once per head and reason, and an unavailable head raises;
  - a real conflict in `_prepare` raises `IntegrationRepairNeeded` naming the path;
  - a generated-only conflict reaches the derived merge;
  - `IntegrationRepairNeeded` routes to `_integration_repair`;
  - a blocked-retryable candidate without a red gate is integrable.
- `tests/test_candidate_lifecycle.py`: the note becomes the reason while state and attempts stay; a later record supersedes it; a note for another head is ignored.
- Spec scenarios: "Derived merge without OpenSpec CLI" is covered by the note and derivation tests; "Real conflict of a waiting candidate" by the prepare, routing and integrability tests.

## Not verified / limits

- No live hosted queue run; GitHub comments and the queue helpers are mocked.
- The Issue title and body of this child still name the earlier conflict-transition scope; the managed package carries the narrowed scope.
