## Context

- `worktree_cleanup.classify` treats a head that is neither an ancestor of main, nor composition-delivered, nor an exact merged PR as `not-merged`; nothing removes it.
- `publication_state.find_exact_head_pr` lists every PR of branch/base (`--state all`) and classifies exact open, exact merged and stale open; a CLOSED exact head is ignored today.
- The agent-board claim of a task lives in `agent_board.board_path(root)`; `agent_board.py finish --id` removes exactly one entry. Doctor (`_safe_to_remove`) removes only entries with proven merge or a missing worktree.

## Decisions

- **Explicit, exact, operator-invoked.** Abandonment is never inferred by `scan` or `cleanup --all`; it needs `cleanup --abandoned` with the exact worktree path, branch and head (the identity the pending report prints). `--abandoned` is refused with `--all`/`--apply` or without the full target.
- **GitHub proves abandonment.** Required: GitHub CLI authentication, an available lookup, an exact-head PR into main in state CLOSED, and no exact merged, exact open or other open PR for the branch. The head must not be an ancestor of main (that is ordinary merged cleanup). Because the removed head is exactly the closed PR's head, GitHub still holds every removed commit (`refs/pull/N/head`); a worktree with commits after the closed head is refused.
- **Same local safety as targeted cleanup.** Registered worktree with matching branch and head, inside the managed worktree directory, not the integration copy, not locked or prunable, clean (`status --porcelain` empty), no process with its cwd inside it (process check must be available), and the local branch ref equals the head.
- **Board claim.** At most one board entry may name the worktree and it must carry the same branch; otherwise refuse (`board-identity-mismatch`). After the worktree and branch are removed, that entry is released through `agent_board.py finish --id`. Doctor logic is untouched; the claim is released only by this exact, proven operation.
- **Truthful result.** Payload `{"status": "completed"|"refused"|"failed", "scope": "abandoned", "target", "pr", "removed", "released_claim", "errors"}`; `refused` and `failed` exit 1 through the existing `cleanup_failed`. No forced removal; a failing `git worktree remove` is `failed`.

## Risks

- Remote branch and the closed PR are left as they are; only local state is removed.
