## 1. Preflight

- [x] 1.1 Identify all platform-owned task-start and expensive full/protected-validation entrypoints on current `main`.
- [x] 1.2 Reproduce `dev-platform#178` with a task branch whose base becomes stale after start.
- [x] 1.3 Confirm current fetch/relation helpers and choose one reusable freshness primitive without creating a second sync mechanism.

## 2. Contract and implementation

- [x] 2.1 Establish an explicit authoritative remote-main observation during supported platform-owned task start.
- [x] 2.2 Add a fresh fetch + task-head ancestry gate immediately before expensive full/protected validation used as delivery evidence.
- [x] 2.3 Return a clear resumable stale/diverged/unavailable outcome without destructive automatic reconciliation.
- [x] 2.4 Preserve `harness_mode=project`, protected-main, exact-head and no-force-push boundaries.

## 3. Regression coverage

- [x] 3.1 Cover fresh task, main-advanced stale task, unavailable remote observation, and successful retry after reconciliation.
- [x] 3.2 Assert the expensive validation command set is not started in the stale controlled case.
- [x] 3.3 Assert fresh tasks execute the same validation commands as before.

## 4. Verification and delivery

- [x] 4.1 Run relevant lifecycle/validation tests and complete required platform validation.
- [x] 4.2 Perform semantic OpenSpec verification and record truthful evidence.
- [x] 4.3 Archive through the normal OpenSpec lifecycle.
- [x] 4.4 If runtime/template code changes, deliver through the ordinary immutable platform release/managed-rollout process.
