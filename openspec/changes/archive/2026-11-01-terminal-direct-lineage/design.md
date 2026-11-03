## Context

`run_terminal(ops, root, number, branch, head, task_identity)` calls `ops.lineage(root, branch)` (`resolve_lineage`, BR branch identity only) and blocks when no child is found for a managed identity. Private mapping markers `<!-- dev-platform-private-lineage:v1:<handle>:<change> -->` live in comments on the private source Issue. `private_lineage.require_handle(root, source, change, handle)` verifies exactly one mapping. The queue resolves trusted authors with `trusted_apps` and `trusted_writers`.

## Decisions

- **Idempotent exit.** `LifecycleOps.terminal_recorded` reads the PR's trusted `dev-platform-lifecycle-result` records. A `pr<N>:terminal-reconciliation:` result whose outcome starts with `task-recorded` ends the job before any walk.
- **Handle.** `LifecycleOps.direct_source` fetches `pull/<N>/head` and requires it to equal the merged head. It finds exactly one `openspec/changes/archive/*-<change>` directory there and reads the handle from its `.managed-task.json` with `git show`. A missing archive or handle is an explicit block.
- **Walk.** `private_lineage.issue_for_handle(root, handle, change, max_pages=20)` pages GraphQL over the open Issues of the configured Backlog repository, 50 Issues per page with the first 100 comment bodies each, and selects candidate Issues: those with the handle in a body, or with more comments than one page holds. Each candidate's comments are then read in full over REST. A marker counts only when `trusted_marker_comment` accepts its author: OWNER, a proven writer via `publication_queue.trusted_writers`, or the coordinator App.
- Exceeding `max_pages` raises "lineage walk exceeded N pages". No marker raises "no open Issue carries this handle (already closed or missing)". Several markers, or a marker naming another change, raise with a reason that names only the Issue number.
- **Verify and act.** `require_handle` runs on the single match, then `ops.reconcile_child`. A reconciliation failure is re-raised naming `Issue #N`. The receipt is `task-recorded: Issue #N`. Neither the handle nor the Backlog repository reaches a public receipt.

## Risks

- The cost grows with the number of open Backlog Issues. The page cap makes growth an explicit error instead of a silent slowdown.
