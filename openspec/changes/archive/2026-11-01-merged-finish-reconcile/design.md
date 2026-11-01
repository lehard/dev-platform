## Context

`finish_task.main` calls `managed_candidate(work)`, and for a candidate it runs `run_finish_preflight` (including the board scope gate) and `finish_developer_handoff`. The merged path (`reconcile_confirmed_remote_pr_merge`, `sync_merged_task`) comes later. `publication_queue.local_status` reads the exact PR state of the branch.

## Decisions

- **Order.** Before the managed-candidate branch, `sync_queue_merged_task` reads the queue status of the branch. If the exact queue PR is merged, it fast-forwards the worktree to the proven merged head (`publication_queue.sync_merged_task`) and finish skips the handoff branch. The existing merged reconcile (`task_pr_is_already_merged` and then `reconcile_confirmed_remote_pr_merge`) now sees the exact merged head. An unreadable queue status or a failed synchronization stops explicitly.
- **Preflight.** The merged reconcile returns before the consolidated preflight, and the handoff branch with its own preflight is skipped. So the board-claim condition never runs for a merged PR, and the preflight registry is unchanged.

## Risks

- One extra PR read per finish of a managed candidate.
