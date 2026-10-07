OpenSpec-Verify: PASS
Verification-Method: semantic OpenSpec review of completeness, correctness and coherence of the delivered change against the completion-lifecycle delta and design
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

`private_lineage.require_clean_candidate` runs the existing `scripts/check_private_backlog_refs.py` over the current candidate only when `[private_lineage] enabled = true`; a missing guard or a non-zero result raises explicitly and no substitute scanner exists. `openspec_lifecycle.archive_change` calls it right after target validation, before the managed identity gate, review, selected checks, evidence writes or OpenSpec mutation (ordinary archive and coordinator finalization). `requirement_integration.publish_candidate` calls it before full candidate validation for complete and draft candidates; the publisher's own recheck is unchanged. Guard diagnostics are forwarded as produced (opaque); the tests assert the private issue number is absent.

Checks actually run: `tests/test_early_private_reference_guard.py` (real temporary Git repositories: proposal reference, archived-artifact reference, missing guard, clean candidate reaching the later gates, opted-out checkout, shared candidate blocked before full checks) and `tests/test_openspec_lifecycle.py` pass; compileall, managed_projects validate and the full test suite (17 groups, including the new test registered in `dev-platform/checks.toml`) passed; docs updated in `docs/engineering/openspec-workflow.md`.

Completeness: tasks 1.1, 1.2, 2.1 and 2.2 are complete (2.2's handoff follows archive). Correctness: behavior matches the delta scenarios. Coherence: proposal, design, tasks and spec describe the delivered behavior.
