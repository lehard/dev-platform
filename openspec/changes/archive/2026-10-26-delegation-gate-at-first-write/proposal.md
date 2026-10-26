## Why

The most frequent manual owner escalation over two weeks (~15 times, last on 2026-10-22): after `route-claude` records a `delegated-child` plan for an R2 task, the supervisor writes the code itself, and the early routing gate only notices in `select_checks`/`run_test_groups`. The task then needs `approve-supervisor-diff` or a rewrite plus a full rerun.

The owner chose variant B on 2026-10-23: delegation is mandatory only when explicitly required; at R2 the supervisor implements itself; for the remaining mandatory cases the violation is caught at the first file write, not in the full run. R3 already stays on the strong supervisor (`complex-parent`) and is unchanged. The owner confirmed this reading on 2026-10-26 (variant A): R2 becomes supervisor-retained, R3 is unchanged, a delegated child is recorded only on an explicit request, and the first-write refusal applies to those explicit routes.

## What Changes

- Route preparation for a routine/standard route on a linked worktree records a `supervisor-retained` plan with the new policy `balanced-parent` by default. The supervisor implements and finalizes with `record-retained-execution`.
- A `delegated-child` plan is recorded only on an explicit delegation request: `dispatch-claude --delegate` / `dogfood_task.py route-claude --delegate`, `prepare --delegate`, and `dispatch-codex` / `route-codex` (which launches the Codex child itself). `complex` keeps `complex-parent` and a standalone clone keeps `parent-only-topology` regardless of the request.
- New `model_routing.py write-gate`: a Claude Code PreToolUse hook for `Write|Edit|MultiEdit|NotebookEdit`. For a target inside an active managed task worktree (outside lifecycle paths) it denies the write when no route exists yet, when the active record has no plan and no execution, or when the plan is `delegated-child` without a real delegation. The denial names the next command. Retained plans and opened delegations pass with no extra step. Targets outside a managed task are not affected.
- `agent_doctor.py` installs the hook idempotently into the integration checkout's machine-local `.claude/settings.local.json` for multi-agent platform-harness projects, next to the git hooks; malformed settings fail explicitly.
- The existing early gate in `status`/`finish`/`run_test_groups`/`verify-routing` and the archive gate stay as the backstop for writes the hook cannot see (shell writes).

## Impact

- `template/scripts/model_routing.py`, `template/scripts/agent_doctor.py`, `scripts/dogfood_task.py`, generated `template/dev-platform/platform-manifest.json`.
- Spec: model-routing ("The platform exposes abstract execution profiles", "Execution path is fixed before task-content mutation", "Routing mismatch fails at routing-adjacent lifecycle commands").
- Docs: `docs/engineering/model-routing.md`, `template/docs/engineering/model-routing.md` where they describe routine/standard delegation.
- Existing in-flight routes keep their recorded plan; a recorded `delegated-child` plan is still honoured and gated.
