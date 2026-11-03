## Why

BR-969 is already in main: main-only integration proof and post-repair reusable-gate carry exist. Composition refresh still uses the older gate predicate and reruns full checks on a new head. After repair a carried full-check gate still names the previous head, so composition publication can fail until a manual advance.

## What Changes

- Reuse the existing main-only proof and post-repair gate carry; do not implement them again.
- Complete clean composition refresh in `publication_queue.refresh_composition_checks`: carry review, finalization and full checks for a proven main-only update.
- Let `require_final_gates` accept proof-bound full-check evidence on the new head without claiming a new check run.
- Require passed required CI on the exact new head before ready and admission; required-check evidence never carries.
- After genuine integration repair, complete final publication once with full checks and admission. Changed own content follows full composition review and finalization first; review is never limited to conflict paths.

## Success evidence

A proven main-only refresh runs no full checks and stays unready while exact-head required CI is pending or failed. Missing proof evidence prohibits reuse. Genuine repair completes one full-check pass and admission without manual advance; changed own content receives full composition review.

## Scope and constraints

BR-969's `main_only_integration`, `main_only_reason` and existing reusable-gate carry in `advance_after_repair` are reused constraints. Preserve child contribution provenance, queue runtime-failure/conflict behavior and required CI. The repair command, queue ordering, advance guard and retrospective boundary belong to the other children.

## Impact

- `template/scripts/{requirement_composition,candidate_lifecycle,publication_queue,integration_contour}.py`, focused tests, generated manifest and composition-gate runbook.
- Specs: platform-lifecycle and publication-queue (added composition-specific rules).

The composition readiness requirements are updated here to permit proof-bound main-only full-check carry and to move the Requirement retrospective to terminal close. Waiting for exact-head CI is recorded durably and resumed by the existing publication queue workflow.
