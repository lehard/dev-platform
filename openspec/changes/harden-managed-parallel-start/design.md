# Design: Transaction-guarded managed parallel start

## Principles

1. **Identity before mutation.** No worktree/branch/board mutation begins for a managed change until a durable, machine-local record of that exact change's start attempt exists on disk.
2. **Scoped locking, not global serialization.** The lock/transaction key is the managed change name. Two different managed changes starting concurrently never contend with each other.
3. **Exact-identity recovery, not best-effort cleanup.** Recovery only ever acts on the single worktree/branch/board entry named by the current task's own transaction record, and only after proving it is safe (no unique commits, no unrelated dirty paths, matching task state, provable exact Git-worktree registration).
4. **Fail closed on ambiguity.** Any state recovery cannot safely interpret (unregistered path, mismatched branch, multiple board matches, unowned dirty files) is left untouched and reported, never guessed at or force-cleaned.
5. **No global pruning.** Managed-start recovery never scans for or removes worktrees/board entries beyond the one exact identity it was asked to start.

## Transaction lifecycle

The transaction is a JSON file under the machine-local worktrees root, keyed by change name (`.managed-start-transactions/<change>.json`), guarded by the existing `locked_json` flock-based helper so concurrent processes serialize safely per file. On first entry for a change, the transaction is created with a fresh `attempt_id`, the resolved worktree path and branch name, and the package identity (`source_issue`, `target_repository`, `change`, `package_revision`). It is persisted to disk *before* the caller's body runs (not only at context-manager exit), so a crash mid-materialization still leaves the receipt for the next retry to find.

On a retry for the same change, the existing transaction's recorded identity is compared field-for-field against the freshly discovered package; any mismatch fails closed with an actionable diagnostic pointing at the transaction file, rather than silently reusing stale identity for a differently-revised package. The transaction is deleted only when the enclosing `start_managed_task` call returns successfully (resume or fresh creation) — an exception propagates and leaves the transaction in place for the next retry.

## Recovery

Recovery runs only when the transaction's worktree does not already carry canonical OpenSpec provenance (i.e. this is not a genuine resume). It reasons entirely from the transaction's own recorded `worktree` and `branch`:

- If none of {worktree path, branch ref, board entry} exist, there is nothing to recover; proceed to a fresh start.
- If the worktree path exists but is not registered as an exact Git worktree (`git worktree list --porcelain`), ownership cannot be proven automatically — fail closed rather than delete an arbitrary directory.
- If task-local state exists at the path but names a different `source_issue`/`change`, fail closed — this is not the requested task's partial state.
- If the branch has commits not reachable from `main`, fail closed — real work would be destroyed.
- If the worktree has dirty paths other than the task's own `.managed-task-state.json` or its own `openspec/changes/<change>/` tree, fail closed — unrelated in-progress work is not discarded.
- A matching board entry is resolved by exact `(worktree, branch)` identity, never by change name alone; more than one match fails closed as ambiguous.

Only once every check passes does recovery call the existing `cleanup_started_task` machinery on that one exact identity, then verifies the worktree, branch and board entry are actually gone before allowing a fresh start to proceed.

## Compatibility

The transaction and recovery path only activate for `profile == "multi-agent"`, matching the existing scope of the worktree/board machinery. The single-worktree (non-multi-agent) start path and the genuine-resume path (`_resume_existing_managed_task`) are unchanged in behavior, only extracted so the transaction wraps them.
