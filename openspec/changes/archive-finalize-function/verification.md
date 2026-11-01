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
- openspec-workflow docs (platform and template) describe the split: a review runs outside archive (the queue review job or the review command), archive only requires its evidence and lists every unmet precondition.

## Correctness

- No defaults: a collected precondition is still a failure; archive raises once with all of them before any selected check, evidence write, rehearsal or OpenSpec mutation. Non-`SystemExit` errors from a gate propagate unchanged.
- The private reference guard still runs before review, selected checks, evidence writes and OpenSpec mutation, as the accepted requirement states.

## Coherence

- Spec delta (one modified, two added completion-lifecycle requirements), proposal, design, tasks and docs describe one archive function, collected preconditions and no review from archive.

## Re-verification after review repair

- Repair `c896f63b` added `finalize_change(root, change, *, context=None)` as a wrapper whose `context` was unused, and left the manifest stale. Replaced by a real single function: `archive_change` is removed and its body is `finalize_change(root, change, *, context)`; `context` is required and selects the executor's gates (`queue`: finalize job; `developer`: own checkout), and an unknown context fails before any work (`test_unknown_context_fails_before_any_work`). The CLI maps `--finalize` to `queue` (`test_cli_selects_the_finalize_context`); the finalize job's `trusted_archiver` runs that CLI (`test_finalize_job_archives_through_the_same_function`). Every test now calls `finalize_change` with an explicit context.
- Privacy ordering restored in substance: the private reference guard tests assert no review launch, no selected checks, no rehearsal, no OpenSpec mutation and no automated-check evidence while the guard blocks; the uncommitted-package test asserts no review launch and no checks.
- Manifest regenerated.

## Re-verification after second review

- Spec-fidelity material (finish launching review is T3's behaviour): the modified completion-lifecycle requirement, the openspec-workflow docs and the review status note now say only that a review runs outside archive and archive never launches it; the finish review stage stays in T3.
- Advisories: task incompleteness is reported once (the separate completed-target problem is removed; the archive-content check reports it); the tautological line-count assertion is replaced by asserting a single task problem; design.md records that target existence (including the change directory read by `static_archive_problems`) stays fail-first and no longer claims dependency reporting between gates.

## Not verified / limits

- Composition finalization and portable finish move onto this function in the next children of BR-949; until then a portable developer archive requires existing review evidence instead of launching the review.
