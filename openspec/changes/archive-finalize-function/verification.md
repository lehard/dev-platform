OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle delta, proposal, design and tasks; targeted unit tests (new test_archive_finalize_function plus the lifecycle, finalization, downstream boundary, private reference, machine pool, independent review, portable finish, template contract, instruction architecture and composition suites); repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Material-design pre-authoring for BR-949; ADD approved by the chat coordinator under the owner's delegation (2026-11-01). This child covers `single-finalize`, `all-preconditions-at-once` and `archive-never-reviews`.
- `archive_change` stays the name of the one finalize function (the queue finalize job reaches it through `openspec_lifecycle.py archive <change> --finalize`); the finalize job harness keeps its commit and path validation, so no second commit path is introduced.
- The target's existence and name stay fail-first (nothing else can be evaluated without them), as do the executor guards (composition outside the coordinator, a developer archive of a coordinator candidate). Every other precondition is collected.
- The `ensure_review_evidence` import and its older-render fallback are removed from `openspec_lifecycle`; archive no longer launches a review on any path.

## Completeness

- One failure listing every unmet precondition: `test_every_unmet_precondition_is_reported_in_one_failure` (incomplete task, missing receipt, missing review evidence and the automated-evidence line together; no checks run, nothing archived).
- No review launch: `test_finalize_lists_missing_review_without_launching_one` (stale review listed, `independent_review.ensure_review_evidence` never called) and `test_archive_module_has_no_review_launcher`; `test_archive_requires_review_evidence_and_never_launches_review` (renamed from the launch test).
- Existing gates now collected: invalid-target tests keep "archive target" naming; the uncommitted-package message is listed with its paths; the private reference guard problem is listed as "archive blocked before review and validation" and nothing is archived; finalize still skips checkout identity, committed package, applicable diff and routing.
- `static_archive_problems` returns every deterministic prerequisite; `require_static_archive_readiness` raises them together.
- openspec-workflow docs (platform and template) describe the split: review runs in the review job (or finish without a queue), archive only requires its evidence and lists every unmet precondition.

## Correctness

- No defaults: a collected precondition is still a failure; archive raises once with all of them before any selected check, evidence write, rehearsal or OpenSpec mutation. Non-`SystemExit` errors from a gate propagate unchanged.
- The private reference guard still runs before review, selected checks, evidence writes and OpenSpec mutation, as the accepted requirement states.

## Coherence

- Spec delta (one modified, two added completion-lifecycle requirements), proposal, design, tasks and docs describe one archive function, collected preconditions and no review from archive.

## Not verified / limits

- Composition finalization and portable finish move onto this function in the next children of BR-949; until then a portable developer archive requires existing review evidence instead of launching the review.
