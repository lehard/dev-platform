## Context

`finish_board()` runs `agent_board.py finish`, which deletes the item. `_required_scope_inputs()` requires an item for the worktree and branch; `_admission_conflicts()` excludes items that are not `valid-active` and honors the current item's `acknowledgments`. `pr_review_gate.handoff_gates()` runs `agent_friction.py assert-checkpoint --exact-head` and no routing gate; `openspec_lifecycle.require_managed_routing_evidence()` is the archive routing gate. `publication_queue.READMISSION_STATES` lists the states a new developer head may supersede.

## Decisions

- **Handed-off record.** `agent_board.py hand-off --id <id> --head <sha> --pr <N>` sets `handed_off: {head, pr, at}` on the item; `claim_eligibility` classifies such an item `handed-off` (never `valid-active`), so it claims no scope for others; terminal problems (merged, missing worktree) still classify it terminal for doctor cleanup. Admission call sites that released the claim (developer handoff, quick-task admission, an active or waiting queue entry) hand off instead of deleting; terminal, manual-review and direct publication still delete.
- **Read-only acceptance.** `_required_scope_inputs` accepts a handed-off current item only when the PR it names is open, its latest trusted coordinator record is in `READMISSION_STATES`, and HEAD descends from the handed-off head; otherwise it refuses naming the state and the command. It writes nothing.
- **Cleanup.** `worktree_cleanup._active_board_paths` skips handed-off records, so an admitted task's worktree is not `active-board` for post-merge cleanup (friction #802 stays fixed); a record whose worktree is gone is removed by `agent_board.py doctor --fix` as before.
- **Reactivation.** `finish_developer_handoff` (advance calls `finish_task.py`), and the terminal-path finish right before `project_publish.py`, run `agent_board.py reactivate --id <id>` after the preflight passed; admission then hands it off at the new head.
- **Checkpoint.** `handoff_gates` runs `assert-checkpoint` without `--exact-head`: the managed task-content proof (BR-940) decides; changed task content still fails.
- **Routing.** `handoff_gates` calls `require_managed_routing_evidence(change)` for an active change before the checkpoint (an archived re-admission passed it at its first handoff); its SystemExit becomes a `WorkerError` with the same text.

## Risks

- While handed off, the task's scope is invisible to other tasks; a sibling may start on the same paths and is caught as a new overlap at the re-handoff.
- A board written before this change has no handed-off items; a task admitted before it still needs one manual `agent_board.py start` at its next re-handoff.
