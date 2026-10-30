OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the publication-queue delta, proposal, design and tasks; targeted unit tests (test_publication_queue, test_autonomous_integration_contour, test_pr_review_gate, test_finish_merged_queue, test_requirement_contribution_composition; test_publication_queue 139 passing); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Direct handoff (deterministic depth, no ADD), implementing the coordinator decision of 2026-10-27 (variant A): the queue's candidate observation retries a transient failure with backoff 15/30/60/120 s; HTTP 422 "too many files changed" is transient only for this read; the shared classification is untouched.
- Absorbed #776: a head-scoped counter `attempts["transient-failures:<head>"]` in the candidate record; `MAX_TRANSIENT_FAILURES` = 3 blocks the candidate with a reason naming head, count and error; reset when an evaluation keeps integration ownership without a transient failure; a new head has its own key.

## Completeness

- Transient 422 then success, every failed attempt logged: `test_transient_422_is_retried_then_the_candidate_is_read`.
- Persistent transient failure names attempts and error; the worker reports `#N not observable` and a run with no observable candidate fails: `test_persistent_transient_failure_fails_naming_attempts_and_error`, `test_worker_names_the_unobservable_pr_and_fails_when_none_is_observable`.
- Non-transient failure not retried: `test_non_transient_failure_is_not_retried`.
- Counter 1, 2, then block with reason: `test_transient_failures_count_per_head_then_block`; new head: `test_a_new_head_counts_from_one`; reset: `test_an_evaluation_without_transient_failure_resets_the_counter`, `test_worker_resets_only_while_the_candidate_keeps_integration_ownership`; the existing `test_transient_failures_wait_instead_of_blocking` now asserts the visible count.
- No real sleeps in tests: `sleep` is a required keyword of `_observe_pr`; the worker passes `time.sleep`.

## Correctness

- Counter writes go through `_transition` with `refuse_from=CLAIM_STATES`, so a claim taken meanwhile is never overwritten (plain wait instead).
- Every failure still raises: an unreadable record (`MalformedRecord`) or failed record publication propagates as before; nothing substitutes a default.

## Coherence

- Proposal, design (reset rule refined to "keeps integration ownership"), tasks and spec delta agree; the platform manifest is regenerated.

## Not verified / limits

- Not exercised against live GitHub; the 422's transience rests on the 2026-10-27 observation recorded in the Requirement (same read succeeded minutes later).
- `ComposeGeneratedManifestConflictTests::test_composition_conflicting_only_in_the_platform_manifest_merges_without_an_operator` fails when run in one process after `tests/test_publication_queue.py`; it fails identically on the unchanged base code and passes alone (pre-existing test-order dependence).
- Existing fallback reported, not changed: `_block` swallows a `QueueError` from its v2 `_transition` (`except QueueError: pass`).
- Independent review round 1: material `transient-block-ignores-claims` fixed (`_transient_wait` checks `_raise_if_owned_elsewhere` before blocking; `test_a_claimed_candidate_is_not_blocked_at_the_limit`); the exhaustion error now names the PR and the design names `_transient_wait`/`_reset_transient`. Advisory accepted: the counter and reset paths re-read the PR and comments with a single attempt, and a failure there raises (the candidate is skipped and named) rather than being counted; this follows the no-fallback rule and leaves the observation retry as the bounded recovery.
