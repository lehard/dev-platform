## Context

`_retention_policy_for(profile, topology)` returns `None` for routine/standard on a linked worktree, and `prepare` turns `None` into `delegated-child`. `require_early_routing_gate` runs only in lifecycle status/finish, the check entrypoint and routing verification, so a supervisor write under a delegated plan is first seen after the code exists.

## Decisions

1. **Default R2 retention.** `_retention_policy_for(profile, topology, *, delegate=False)`: `complex` -> `complex-parent`; standalone clone -> `parent-only-topology`; explicit `delegate` -> `None` (delegated child); otherwise `balanced-parent`. `_retention_policy(route)` returns `None` for a recorded `delegated-child` plan so an in-flight delegated route can never be finalized as retained by recomputation.
2. **Explicit delegation is a caller request, not a hidden default.** `prepare(..., delegate=True)` is reached from `--delegate` on `prepare`/`dispatch-claude` and from `dispatch_codex`, whose purpose is launching the child. The plan still records the mode; no new plan field is needed.
3. **Write-time gate as a Claude PreToolUse hook.** `write-gate` reads the hook JSON, resolves the target's git worktree (nearest existing ancestor), and applies `check_task_write(root, target)`. Outside a git worktree, outside an active managed task, or on a lifecycle path it allows. Otherwise it reuses the early-gate rules prospectively (the write itself is the divergence). Denial is exit code 2 with the reason and the next command on stderr; any internal error also denies with its message (fail closed only inside a managed task).
4. **Installation.** `agent_doctor.py` already installs git hooks for multi-agent platform projects; it now merges one PreToolUse entry running `python3 "$CLAUDE_PROJECT_DIR/scripts/model_routing.py" write-gate` into `<integration>/.claude/settings.local.json` (machine-local, git-ignored). Present entry -> no change; invalid JSON or a non-object `hooks` -> explicit failure. Sessions started before installation pick it up on restart; shell writes stay covered by the existing early gate.

## Risks

- Shell-based writes bypass the hook; the existing early gate remains the backstop and is unchanged.
- Sessions rooted directly in a task worktree do not load the integration checkout's settings; documented.
