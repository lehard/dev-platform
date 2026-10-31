OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle delta, proposal, design and tasks; new and updated unit tests on a real Git repository and the integration contour; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Coordinator decision D1=B with conditions (2026-11-01): a three-way proof; the old head comes only from a trusted queue record; a missing record resets explicitly; the tree comparison is byte-exact; generated files are excluded only by the default-branch declaration.
- `task_content_identity.main_only_integration` runs `merge-tree` on the old head and the new base. Conflicts must lie only in `generated`, and `git diff` of the merge tree against the new head's tree must list no path outside `generated`. A malformed SHA returns a reason; a Git failure raises `IntegrationProofError`.
- `integration_contour.main_only_reason` takes the old head from the trusted derived candidate, the exact-head record that carries the gates, and the generated set from `generated_files(root, "HEAD")` of the coordinator checkout.
- `advance_after_repair(..., base=outcome["main"])` keeps the gates that are reusable for the gated identity, rebound to the fresh identity, and moves the candidate to ready. Required checks never carry over. Otherwise the candidate returns to review and the reason goes to the worker log.

## Completeness

- `tests/test_task_content_identity.py` `MainOnlyIntegrationTests`, on a real Git repository:
  - a main merge that touches a shared task path (checks.toml), with a regenerated manifest, is proven;
  - an own edit after the merge is not proven, and the reason names the path;
  - an empty generated declaration does not exclude the manifest;
  - a missing head returns a reason, and an unknown object raises.
- `tests/test_autonomous_integration_contour.py`:
  - a proven integration keeps the semantic gate, rebound to the fresh identity, and drops required checks;
  - an unproven integration returns to review and logs the reason;
  - a missing trusted gated head yields the reason.
- Spec scenarios:
  - "Main touched a task path" is covered by the proof and contour keep tests;
  - "Integration changed own content" by the own-edit and return-to-review tests;
  - "No trusted record" by the `main_only_reason` test.

## Not verified / limits

- No live hosted integration repair run; the contour tests use the queue fixture.
- The derived merge in the queue's `_prepare` keeps its existing gate handling. This change covers the integration-repair path, which reset the receipts of #836 and #837.
- The reset reason goes to the worker log, not to a PR record.
