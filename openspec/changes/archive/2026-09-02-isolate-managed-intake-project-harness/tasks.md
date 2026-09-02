## 1. Compatibility boundary

- [x] Trace and remove unconditional managed-start imports from project-owned
  publication modules.
- [x] Define the smallest platform-owned interface needed by platform-only
  pending-rollout reconciliation and document its harness-mode gate.

## 2. Regression coverage

- [x] Add a Jara-shaped project-harness fixture that lacks the platform
  `PrRef` API and prove a valid task completes standard managed start.
- [x] Cover fail-closed pre-admission behavior with no partial worktree, board
  or Project-status mutation.
- [x] Retain/add a platform-harness exact-head pending-rollout regression.

## 3. Verification and delivery

- [x] Run the mapped managed-task and rollout test groups plus required
  platform validation; record actual evidence.
- [x] Update the managed OpenSpec contract, archive only after semantic
  verification, and deliver through the ordinary protected-main lifecycle.

## Implementation notes

- `PrRef` now has its canonical definition in `publication_state.py` (an
  always-platform-owned module every harness renders); `project_publish.py`
  re-exports it, so `project_publish.PrRef` and every existing importer keep
  working.
- `rollout_preflight.py` top-level imports are platform-owned only
  (`_platform_common`, `integration_state`, `publication_state`,
  `rollout_identity`). `serialized_integration` is imported from
  `integration_state` directly instead of via `finish_task`.
- `request_protected_merge` (from `project_publish`) and
  `sync_after_remote_pr_merge` (from `finish_task`) are loaded lazily by
  `_load_platform_reconciliation_helpers()`, called only after
  `reconcile_pending_rollout` confirms `harness_mode=platform` and an
  unambiguously green rollout — a proven platform-harness-only operation.
- `reconcile_pending_rollout` self-gates: `harness_mode=project` returns
  `NONE` without observing or importing publication code; a missing
  platform-owned dependency in platform mode raises
  `PlatformPublicationUnavailable`, translated to `BLOCKED` before any merge,
  sync, worktree, board or status side effect.
