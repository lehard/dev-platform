## Context

- `requirement_terminal.reconcile_parent(root, ...)` calls `managed_task.resolve_canonical_provenance(root, ...)`, which globs `root/openspec/changes/archive`. Callers: `finish_task.reconcile_linked_parent` (after `sync_after_remote_pr_merge`, so main is current), the post-merge `terminal-reconciliation` job (`integration_contour.run_terminal`, root = worker cwd, no sync), `execute_requirement.advance` single-child and recovery paths (no sync).
- `execute_requirement._done_child_is_delivered` has the same checkout read.
- `managed_task.target_main(root)` already fetches `origin/<main_branch>` and returns its commit.
- Post-merge finish: for a queue-merged task `finish_task.main` takes `sync_merged_task` and then `task_pr_is_already_merged` -> `reconcile_confirmed_remote_pr_merge`, which returns before `observe_completion_blockers` (the only place `enforce_scope_gate` runs on that path); `finish_board` is a no-op without a claim.

## Decisions

- **Read the fetched commit, never move the checkout.** Proof comes from `git ls-tree`/`git show` of the fetched `origin/main` commit. The integration checkout is not fast-forwarded, switched or given a worktree; that keeps the rule that only post-merge `finish` advances integration `main`. The existing "integration main branch" precondition of `reconcile_parent` stays.
- **One shared resolver, same semantics.** `managed_task.resolve_committed_lineage(root, commit, source_issue=, change=)` lists the active and archived (`archive/*-<change>`, legacy `archive/*/<change>`) locations holding `.managed-task.json` in the commit, materializes only those provenance files and `verification.md` into a temporary directory, and validates each with the existing `_provenance_for` (so private-lineage handles are authorized against `root`'s configuration). Foreign-source or ambiguous lineage fails closed exactly like `resolve_canonical_provenance`; no lineage returns `None`. It returns the lifecycle and whether the receipt exists, never a temporary path.
- **Fetch once per reconciliation.** `reconcile_parent` fetches before the child loop; `_done_child_is_delivered` fetches per call (a handful of children). A failed fetch raises; nothing falls back to the checkout.
- **Claimless post-merge finish is a regression test only.** No code change: the test drives `finish_task.main` with a real board file that has no claim for the worktree and a required scope gate, and asserts completion, an untouched board, and that the same board would fail the scope gate if reached.

## Risks

- Terminal reconciliation now needs network access to `origin`; it already needs GitHub for Issues and Project state.
