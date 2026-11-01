## Context

`integration_contour.advance_after_repair` and `post_review_finalization.reestablish_gates` decide gate reuse through `pr_review_gate.reusable`, which calls `task_content_identity.equivalent_proofs`. A task-content proof records `base`, a digest and per-path blobs, but no head. Queue transitions are PR comments; trusted writers and the coordinator App are resolved by the queue (`trusted_apps`, `trusted_writers`). Declared generated files come from `dev-platform/checks.toml` `generated_files`.

## Decisions

- **Proof.** `task_content_identity.main_only_integration(root, old_head, new_base, new_head, generated)` runs `git merge-tree --write-tree --name-only --no-messages <old_head> <new_base>`. It holds only when every conflicted path is in `generated` and `git diff --name-only <merge tree> <new_head>^{tree}` lists no path outside `generated`. Trees are compared by object id, so the comparison is byte-exact. Generated content is validated by its own `--check`, as today. A malformed SHA returns a reason. A Git failure, such as a missing object, raises `IntegrationProofError`.
- **Old head.** `integration_contour.main_only_reason` takes the old head from the derived candidate, that is, the latest trusted exact-head record whose gates are bound to the receipt. A missing head or missing gates yields the reason "no trusted queue record names the head on which the gates passed". The candidate's own files are never a source.
- **Generated declaration.** `main_only_reason` reads `generated_files(root, "HEAD")` from the coordinator's default-branch checkout, the same source `_prepare` uses. It never reads the candidate.
- **Use.** `advance_after_repair(..., base=outcome["main"])` keeps the gates that are reusable for the gated identity, rebinding them to the fresh identity, and moves the candidate to ready, the same way it handles unchanged content. Required checks never carry over. An unproven integration returns to review as today, and the reason goes to the worker log. Finalize needs no change, because the rebound gates match the fresh identity.

- **Derived merge.** A derived merge that changes the task-content identity raises `RederivationFailed`, and `_prepare` routes that to integration repair. That round reaches `advance_after_repair`, so the derived-merge route is covered at the same point.
- **Unproven outcome.** `return_to_review` repeats review. Finalize's `reestablish_gates` then raises `SemanticVerificationRequired`, which sends the receipt reset back to the developer through handoff, as today.

## Risks

- A Git failure in the proof after the repaired head was pushed (`IntegrationProofError`) stops the integration-repair job explicitly, with no transition. The existing validated-push recovery only adopts an identical digest, so such a candidate waits for an operator or a developer re-handoff instead of being adopted silently.

- The proof needs the old head and new base objects locally. A missing object raises an explicit error, it is never treated as a mismatch.
