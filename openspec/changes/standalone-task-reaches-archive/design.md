## Context

`STANDALONE_CLONE` means the task root is the integration copy. The only writer is the supervisor (child writers are refused there by `_refuse_child_writer_on_standalone_clone`), so the containment postcheck can only mean: nothing happened to the copy except the supervisor's own task. `_postcheck` already removes platform lifecycle entries for this topology.

## Decisions

- **Option A (coordinator-reviewed): commits are the task, leftovers are not.** For `standalone-clone` and a route with no delegated child (`_no_delegated_child_ran`), a pure HEAD move is accepted when `git merge-base --is-ancestor <snapshot head> <current head>` holds and the working tree has no new, changed or vanished path after lifecycle entries are removed. A pre-existing dirty path whose status or fingerprint changed stays a new change. A non-descendant HEAD (reset, other branch, rebase of earlier history) stays a violation. The accepted move is recorded as `task_commits`. Rejected: B (requiring committed paths to match a declared scope: managed tasks often declare none, so it would block valid work and needs a new scope contract) and C (skipping the postcheck: nothing would catch leftovers).
- **Linked-worktree routes are unchanged.** Their postcheck still guards the integration copy from the task.
- **Hints name existing commands.** `model_routing.py prepare --provider claude|codex ...` is the real entry; `begin-claude-delegation` is a `model_routing.py` subcommand. `dogfood_task.py` is platform-only and is not named in shipped text; `finish_task.py --status` is the shipped status command if it ships (checked against `template/scripts`).
- **State file ignore is local.** `managed_task` appends `.managed-task-state.json` to `$(git rev-parse --git-path info/exclude)` when `git check-ignore` does not already ignore it; the project-owned `.gitignore` is not edited. A write failure raises naming the path.

## Risks

- A supervisor commit outside the task is not detected in this topology (it is the supervisor by definition); the review of the PR remains the guard.
