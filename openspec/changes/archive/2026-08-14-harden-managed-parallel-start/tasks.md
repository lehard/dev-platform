## 1. Start transaction

- [x] 1.1 Reproduce the concurrent-start-state-leak class from process issue #262 (unrelated sibling task's stale board/worktree state blocking a fresh task's start).
- [x] 1.2 Persist a machine-local, per-change start transaction before any worktree/board mutation, locked so only retries of the same change serialize.
- [x] 1.3 Persist the transaction before the caller's body runs (not only at context-manager exit) so a crash mid-materialization still leaves a retry receipt.
- [x] 1.4 Retire the transaction only after the enclosing start call actually completes (resume or fresh creation).

## 2. Exact-identity recovery

- [x] 2.1 Distinguish a canonical existing task (matching active/archived OpenSpec provenance) from bounded incomplete creation state.
- [x] 2.2 Recover only the exact registered worktree/branch/board entry named by the current task's own transaction.
- [x] 2.3 Refuse recovery when the candidate has unique commits not on `main`, unrelated dirty paths, mismatched task state, an ambiguous board match, or cannot be proven as an exact registered Git worktree.
- [x] 2.4 Never run global worktree/board pruning as part of managed-start recovery.

## 3. Verification

- [x] 3.1 Add regression coverage: transaction receipt exists before workspace mutation and is retired after success.
- [x] 3.2 Add regression coverage: an interrupted start preserves the receipt for retry.
- [x] 3.3 Add regression coverage: an exact partial task is recoverable without touching an unrelated dirty sibling worktree.
- [x] 3.4 Add regression coverage: board lookup is fenced to exact task branch/worktree identity even with stale sibling state present.
- [x] 3.5 Add regression coverage: unregistered/non-canonical paths are left untouched rather than guessed as retry debris.
- [x] 3.6 Run relevant managed-task, OpenSpec lifecycle, template/render and strict validation checks selected by current risk policy.
- [x] 3.7 Perform semantic OpenSpec verification and archive through the normal lifecycle.
