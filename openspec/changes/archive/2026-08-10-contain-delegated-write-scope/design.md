# Design: delegated write containment

## What the runtimes actually give us today

This section states capability facts, not aspirations. Claims below are sourced from Claude Code's published hooks reference and Codex CLI's published sandboxing documentation (see verification.md for links). Anything not confirmed here is treated as unavailable.

### Claude Code

- Hooks (`PreToolUse`, `PostToolUse`, ...) are user/project-configured shell commands declared in `settings.json`. `PreToolUse` runs **before** a tool executes and can block it (exit code `2` plus `permissionDecision: "deny"` in the hook's JSON output stops the tool call outright). This is a real pre-write interception point, not just after-the-fact logging.
- There is **no native filesystem sandbox**: nothing in Claude Code itself restricts which paths a `Bash`, `Edit`, `Write`, or `NotebookEdit` call may touch. Any restriction has to be implemented as a `PreToolUse` hook that inspects the tool's input (the `file_path` argument for `Edit`/`Write`, or the raw command string for `Bash`) and denies calls that resolve outside an allowed root.
- The `Agent`/`Workflow` tools' `isolation: "worktree"` option creates a separate `git worktree` for a subagent. That is real containment **for git history and branch state** (the subagent's commits land on a different branch/directory than the parent's checkout) — but it is a git construct, not a filesystem permission boundary. A subagent inside an isolated worktree can still write to an absolute path outside that worktree if nothing stops it (see the hook point above).
- Whether a spawned subagent inherits the parent session's `settings.json` hooks is a property of how the harness wires up the child process, not something this design can assert as universally guaranteed. Treat hook coverage of delegated subagents as something the caller must verify for its own harness, not as a given.

**Conclusion for Claude Code:** the only real pre-write enforcement point is a `PreToolUse` hook that checks the resolved absolute path of `Edit`/`Write`/`NotebookEdit` targets and the `cwd`-resolved effect of `Bash` commands against `assigned_worktree`, denying anything outside it. Where that hook is not installed or does not cover a given tool, this design falls back to detection-after-the-fact (below) — it does not claim hard prevention in that case.

### Codex

- Codex CLI enforces its sandbox (`read-only` / `workspace-write` / `danger-full-access`) at the **OS level** — Landlock + seccomp on Linux, Seatbelt on macOS, an analogous mechanism on Windows — via a `SandboxPolicy` that names writable roots. This is enforced by the kernel/OS for the spawned process tree, not by agent-side logic, so it holds even if the model itself tries to escape it.
- `workspace-write` with the writable root set to `assigned_worktree` is real, kernel-enforced hard containment: a write syscall outside that root fails at the OS level regardless of what command or absolute path the agent tries.

**Conclusion for Codex:** where the platform controls how a Codex subagent is launched, setting its sandbox writable root to `assigned_worktree` is genuine prevention, not just detection.

### Where the platform (dev-platform) controls subprocess launch directly

For any subprocess/subagent this platform's own scripts spawn directly (not through an external agent runtime's own delegation mechanism), always launch with `cwd=assigned_worktree`. This is a partial mitigation only — it sets the default relative-path root but does not stop an absolute-path write or an explicit `cd`. It is still worth doing because it is free and closes the common accidental case.

## The contract

Every write-capable delegation carries:

```
assigned_worktree: <absolute path, must be a registered git worktree of integration/main>
```

Before delegating:

1. Resolve `assigned_worktree` to an absolute, real (symlink-resolved) path and confirm it is a registered worktree (`git worktree list --porcelain`) distinct from the integration copy itself.
2. Snapshot `integration/main`: `git rev-parse HEAD` plus `git status --porcelain --untracked-files=all`, captured as a set of `(path, status)` pairs. This snapshot captures pre-existing dirty state; it is not a judgment about whether that state is "clean."
3. If the runtime offers a real pre-write enforcement point (Claude Code `PreToolUse` hook, Codex sandbox writable root), wire `assigned_worktree` into it before the subagent starts.
4. Launch the subprocess/subagent with `cwd=assigned_worktree` when the platform controls the launch.

After delegation returns (success or failure — always run this):

5. Re-snapshot `integration/main` the same way.
6. Compute the diff between the two snapshots. Paths present in both snapshots with the same status are pre-existing and are never treated as a violation, even if they look suspicious — they were not introduced by this delegation and must not be touched.
7. Any path that is new in the post-snapshot, or whose status changed, is a **new change**. If `integration/main` is not the assigned worktree for this delegation, every new change is a containment violation.
8. On violation: fail closed. Do not report the delegation as successful. Do not run `git stash`, `git reset`, `git clean`, or delete anything — the changed paths may be another agent's legitimate concurrent work; the safest action is to stop and report, never to "clean up" state this component does not own.
9. Only after step 6/7 has run (so we know we are not about to log a false positive against pre-existing dirty state) record a friction event via `agent_friction.py`, describing exactly which path(s) were touched outside `assigned_worktree`. Friction logging must not depend on GitHub auth — it is a local JSONL append, so record the incident even when GitHub is unreachable.

## Fail-closed scope

- A pre-existing dirty `integration/main` (dirty before delegation even started) is never auto-touched. It is reported once, distinctly from any new violation, so a human can tell "this was already here" from "this just happened."
- If the pre- or post-snapshot step itself fails (e.g. `git status` errors), treat that as a containment check failure and fail closed — do not assume "no violation" by default.
- This design does not attempt to detect containment violations inside the assigned worktree itself (a subagent is expected to write there) or across two different assigned worktrees delegated concurrently to different agents (that is existing worktree-isolation territory, already covered by the platform's worktree/board/lock model).

## Explicit limitation

For Claude Code specifically, without a correctly configured and inherited `PreToolUse` hook, this contract is **detection, not prevention**: a containment violation is caught after it happened, reported, and failed closed — the write itself was not blocked. This limitation is recorded here rather than glossed over, per the platform's no-fabricated-verification principle.
