OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the chat-coordinator delta against `template/scripts/lifecycle_overview.py`, proposal, design and tasks; targeted unit tests (`tests/test_lifecycle_overview.py`); `openspec validate --strict`; repository-owned selected checks recorded by the lifecycle (full suite)
Automated-Checks-Evidence: automated-checks.json

## Completeness

- Every scenario of the delta has a test in `IdleReasonTests`: local macOS node job (`test_unclaimed_integration_repair_waits_for_the_local_macos_node`), developer (`test_pr_without_lifecycle_record_waits_for_the_developer`), queue (`test_ready_candidate_waits_for_the_publication_queue`), attempt limit (`test_exhausted_attempt_limit_is_named`), unknown (`test_unestablished_reason_is_shown_as_unknown_never_hidden`).
- No idle reason for a claimed job or a merged PR: `test_claimed_job_and_merged_pr_have_no_idle_reason`; every candidate state gets a reason: `test_every_candidate_state_gets_an_explicit_reason`.
- Unreadable candidates carry an explicit unknown idle reason in `observe_candidate`.

## Correctness

- Rules read only fields the assessment already holds; limits come from `pr_review_gate.MAX_ROUNDS` and `publication_queue.MAX_INTEGRATION_REPAIRS`; the hosted/local split comes from `hosted_workers.UNHOSTED`. The macOS wording is used only for `repair` and `integration-repair`, the kinds with a sandboxed local writer; other unhosted kinds say "local operator node".
- The overview stays read-only; no action is taken on a reason.

## Coherence

- `idle` is additive: `expected_automation`, findings and stages are unchanged and their tests pass. `docs/engineering/chat-coordinator.md` describes the new line. The platform manifest was regenerated for the changed template script.
- Limitation: a state whose job is already completed but not yet advanced reports "idle reason unknown" rather than a guess.
