## 1. Archive preflight

- [ ] 1.1 Add `archive_content_problems(root, changes)` (tasks complete; new-capability delta Purpose present and not a placeholder, in order) to `template/scripts/openspec_lifecycle.py` and call it from `require_static_archive_readiness`.
- [ ] 1.2 Add the committed-package gate for non-finalize archive with the lifecycle-evidence exemption and an actionable diagnostic.
- [ ] 1.3 Add `openspec_failure_summary` and the disposable-copy rehearsal of archive plus strict validation before mutation.
- [ ] 1.4 Capture `openspec/` before the real archive and restore it on post-validation failure with a rerun instruction.

## 2. Callers

- [ ] 2.1 Use the failure summary in `post_review_finalization.trusted_archiver` and `_openspec` instead of the 400-character tail.
- [ ] 2.2 Call the readiness predicate in `pr_review_gate.handoff_gates`.
- [ ] 2.3 Call it in `requirement_composition.publish_composition` before offering review, in `execute_composition_review` before launching reviewers, and in `execute_composition_finalize` before archiving any child.

## 3. Docs and tests

- [ ] 3.1 Document delta `## Purpose`, the committed-package gate, rehearsal and recovery in `docs/engineering/openspec-workflow.md`.
- [ ] 3.2 Tests: end-to-end new capability archive with authored Purpose passes `validate --all --strict`; missing/placeholder Purpose and uncommitted package fail before mutation; rehearsal failure leaves the tree unchanged; forced post-validation failure restores the tree and a rerun succeeds; finalization error contains the failing item; handoff/composition readiness blocks before review; hygiene exact-target exemption still holds.
- [ ] 3.3 Exercise the archive on a rendered downstream template project and record the result.
- [ ] 3.4 Regenerate the platform manifest; run required validation, semantic verification, archive, retrospective and publication.
