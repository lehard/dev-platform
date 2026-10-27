## Why

`start_task` runs `agent_doctor`, which runs `agent_board.py doctor --fix`. The doctor classifies every registered branch that is an ancestor of `main` as `merged-branch` and removes the entry when its worktree is clean. A task that another session has just registered has a branch created from the main tip and no commits yet, so it is an ancestor of `main` and its entry is deleted from the board. The owning session loses its scope claim and has to re-register. The earlier read-modify-write race hypothesis was refuted: every board writer goes through `locked_json`, and 16 processes x 150 iterations kept 2400/2400 entries.

## What Changes

- `agent_board.py start` records the branch head at registration (`base_head`) in the board entry.
- When a registered branch is an ancestor of `main`, the doctor treats it as merged only with proof:
  - the branch still points at its recorded `base_head`: the task has no own commits; it is active and gets no merge problem;
  - the branch moved on from `base_head` (which stays its ancestor) and its tip is not on main's first-parent line since `base_head` (the tip entered main as a merge parent): `merged-branch`, as today;
  - otherwise an exact merged GitHub PR for the branch: `merged-pr`, as today;
  - otherwise the entry gets a named `unproven-merge-*` problem, is classified degraded and is never removed.
- `doctor` text and JSON output name the reason for each `unproven-merge-*` problem.
- No fallback: an entry whose merge cannot be proven is refused for removal, not guessed.

## Impact

- `template/scripts/agent_board.py` (`cmd_start`, `_status`, `cmd_doctor`).
- Tests: `tests/test_worktree_hygiene.py`.
- Spec: worktree-coordination.
- Existing board entries created before this change have no `base_head`; when their branch is an ancestor of `main` and no exact merged PR proves the merge, they are reported `unproven-merge-no-base` and kept until their task finishes normally.
