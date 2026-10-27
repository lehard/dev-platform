## Why

`worktree_cleanup.py` removes only worktrees whose head is merged (ancestry, exact merged PR or Requirement composition manifest). A candidate whose PR was closed without merge stays forever as "not-merged" in the pending report, together with its local branch and, for non-coordinator tasks, its agent-board claim. The board doctor correctly refuses to remove such a claim because nothing proves a merge (BR-778). Operators remove these worktrees by hand with `git worktree remove --force` and `git branch -D`, which skips every safety check.

## What Changes

- `template/scripts/publication_state.py`: `ExactHeadPrLookup` also reports `exact_closed`, the PR for the branch/base whose exact head is CLOSED without merge (more than one is unavailable).
- `template/scripts/worktree_cleanup.py`: `cleanup --abandoned` with the exact `--worktree/--branch/--head` target. It proves abandonment from GitHub, checks the worktree is safe to remove, removes the worktree (no force) and the local branch, and releases this worktree's exact board claim. A refusal names its reason and exits non-zero; a failed step reports `failed`.
- Tests for each refusal and the success path.

## Impact

- `template/scripts/publication_state.py`, `template/scripts/worktree_cleanup.py`, tests, platform manifest.
- Spec: worktree-coordination (one added requirement).
- `agent_board.py` doctor and `_safe_to_remove` are unchanged.
