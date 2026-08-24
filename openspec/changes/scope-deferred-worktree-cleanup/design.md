# Design: Task-scoped deferred cleanup

## Decisions

1. **Targeted is the default.** Cleanup invoked as follow-up to one managed task requires an exact deferred record/task/worktree selector.
2. **Global is explicit.** Processing all eligible deferred records requires `--all`; no bare cleanup command may silently imply it.
3. **Preview before global mutation.** `--all` exposes the bounded set of candidates and refuses ambiguous/unprovable entries rather than guessing.
4. **Identity before deletion.** Existing branch/head/worktree/process/board/cleanliness checks remain authoritative and are applied to each exact record.
5. **No unrelated state mutation.** Targeted cleanup must not delete, reset, stash, clean or otherwise change any other worktree.
6. **Recovery stays idempotent.** Repeating a completed targeted cleanup produces a safe no-op/result rather than acting on a replacement path.
