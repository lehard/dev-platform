OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the publication-queue delta, proposal, design and tasks; new and updated unit tests; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- On 2026-11-01 the coordinator narrowed BR-969 item 2 (variant A). The conflict path already exists: `_prepare` detects conflicts through `merge-tree`, a real conflict becomes counted integration repair, and a generated-only conflict takes the derived merge. GitHub mergeability is not read.
- `publication_queue._note_environment_error` posts a v1 `environment-error` event with the exact head and failure. It skips the post only while the derived candidate already shows that reason for the head, and raises when the head is unavailable. `_integrate` calls it in the `QueueEnvironmentError` handler, after releasing the active label and before re-raising. It records no transition, block or job. A failed note raises `QueueEnvironmentError` naming both failures.
- `candidate_lifecycle.derive_candidate` remembers the last environment-error event for the current head. When that event is newer than the latest exact-head v2 record and the state is ready, integrating or blocked-retryable, the reason becomes "coordinator environment error on this head: …". State, gates and attempts are unchanged. The v1-only fallback ignores these events.

## Completeness

- `tests/test_publication_queue.py`:
  - `_integrate` on an environment error records no transition, job or block and calls the note once with the exact head;
  - the note is posted only while it is not already the shown reason, so a recurrence after a newer record is posted again, and an unavailable head raises;
  - a failed note keeps the environment error and names both failures;
  - a real conflict in `_prepare` raises `IntegrationRepairNeeded` naming the path;
  - a generated-only conflict reaches the derived merge;
  - `IntegrationRepairNeeded` routes to `_integration_repair`;
  - a blocked-retryable candidate without a red gate is integrable.
- `tests/test_candidate_lifecycle.py`: the note becomes the reason while state and attempts stay; a later record supersedes it; a note for another head is ignored and never replaces this head's reason text.
- Spec scenarios: "Derived merge without OpenSpec CLI" is covered by the note and derivation tests; "Real conflict of a waiting candidate" by the prepare, routing and integrability tests.

## Independent review

- Three advisory findings (engineering-quality, spec-fidelity) are fixed. A note superseded by a later record is posted again when the same failure recurs. The reason text comes only from the current head's note. A failed note no longer hides the environment error.

- Two advisories from the re-review are kept as they are.
  - The note posts the coordinator's environment-error text on the PR. That text comes from platform messages, is capped at 500 characters, and goes to the same public surface as the existing block reasons.
  - The note-failure path catches `QueueError`, which is what the queue's `gh` helpers raise. Any other exception still propagates explicitly.

## Composition repair 2026-11-01

- Composition review of #843 found BR-969 item 3 unmet: a conflicting waiting candidate whose derived merge hits an environment failure stayed blocked-retryable. Repair 1c210eda routed it to `IntegrationRepairNeeded`. This developer fix names both causes in the reason, aligns design, spec and tasks (the environment note now applies only without a real conflict), adds the tests and regenerates the manifest.
- Tests: `test_unavailable_derived_merge_with_a_real_conflict_needs_integration_repair` covers the conflict branch, with a reason naming the conflict and the environment failure. `test_environment_failure_is_a_queue_environment_error` covers the no-conflict branch, which raises `QueueEnvironmentError` with no GitHub write. `test_integrate_releases_ownership_and_records_nothing` covers the note path.

## Not verified / limits

- No live hosted queue run; GitHub comments and the queue helpers are mocked.
- The Issue title and body of this child still name the earlier conflict-transition scope; the managed package carries the narrowed scope.
