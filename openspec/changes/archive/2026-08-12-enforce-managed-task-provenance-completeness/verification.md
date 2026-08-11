# Semantic OpenSpec verification

OpenSpec-Verify: PASS
Verification-Method: equivalent manual completeness-correctness-coherence review

Reviewed the managed-task intake, resume, publication and terminal-reconciliation paths against this change's proposal, design and delta specs.

- Completeness: task-level managed identity, active and archived canonical provenance, mismatched/missing lineage, package evolution, incomplete archive evidence, and direct current-spec drift are covered by contract tests.
- Correctness: the original transport package is never reapplied during resume; publication only accepts the matching archived change with completed tasks and a successful verification receipt.
- Coherence: `start_managed_task.py`, `managed_task.py`, `project_publish.py`, `finish_task.py`, and Project-status discovery use the same source-issue/change identity; quick tasks without managed identity remain unaffected.

Validation evidence: targeted managed-task/lifecycle tests (47 tests), complete repository test suite, Python compilation, managed-project registry validation, lifecycle hygiene, and strict OpenSpec validation all passed on 2026-08-12.

Follow-up review found that minimal pre-managed-intake render fixtures omit `managed_task.py`. `finish_task.py` and `project_publish.py` now retain a no-op import fallback only for that legacy render shape; the current template imports and enforces the guard. The complete repository suite was rerun after this compatibility repair.
