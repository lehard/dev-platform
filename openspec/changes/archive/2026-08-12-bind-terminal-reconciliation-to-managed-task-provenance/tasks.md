## 1. Preflight and bootstrap

- [x] 1.1 Trace `.managed-task-state.json` creation, tracking, inheritance, resume checks and cleanup from Development Backlog #15 through current `main`.
- [x] 1.2 Reproduce the current bootstrap blocker: stale state B in integration, fresh package A, no canonical A before materialization.
- [x] 1.3 Establish a bounded, reviewable bootstrap/recovery path that creates the exact #18 task checkout and materializes this package without treating #15 state as #18 resume evidence.
- [x] 1.4 Trace managed source identity from successful materialization through publication, exact-head merge, local reconciliation, Project-status update and cleanup.
- [x] 1.5 Confirm overlap with the active `adopt-gh-aw-process-automation` change and preserve the dependency that this fix lands first.

## 2. Contract and implementation

- [x] 2.1 Make fresh-start versus resume classification deterministic and immune to inherited task state from integration.
- [x] 2.2 Ensure task-specific state cannot remain authoritative across unrelated tasks; choose the smallest safe locality/cleanup/classification mechanism.
- [x] 2.3 Preserve #15 provenance-completeness guards for genuine managed resume after task-local identity exists.
- [x] 2.4 Add deterministic task-local terminal identity handoff using existing managed provenance/publication primitives.
- [x] 2.5 Make integration-visible managed state a cross-check only at terminal boundaries and fail closed on mismatch before Project mutation.
- [x] 2.6 Ensure confirmed remote merge remains authoritative when managed/local reconciliation is pending.
- [x] 2.7 Keep quick-task behavior and repository-local OpenSpec canonical semantics unchanged.

## 3. Regression coverage

- [x] 3.1 Add a regression test for fresh start A from integration containing stale state B before A materialization.
- [x] 3.2 Prove genuine resume A with matching active/archived canonical provenance still passes and missing/mismatched provenance still fails closed.
- [x] 3.3 Add tests reproducing `dev-platform#166`, `#174`, and `#177` with task A versus stale task B identity.
- [x] 3.4 Cover multiple archived packages, matching identity, mismatch blocker, retry/idempotence, and quick-task no-op behavior.
- [x] 3.5 Verify neither bootstrap nor terminal recovery can mutate or adopt a Development Backlog item other than the exact task source.

## 4. Verification and delivery

- [x] 4.1 Run relevant managed-task/lifecycle tests plus complete required platform validation selected by the current contract.
- [x] 4.2 Perform semantic OpenSpec verification and record truthful evidence.
- [x] 4.3 Archive the change through the normal OpenSpec lifecycle.
- [x] 4.4 If runtime/template code changes, publish through the ordinary immutable Dev Platform release flow; do not start `development-backlog#5` until this change is terminally delivered.
