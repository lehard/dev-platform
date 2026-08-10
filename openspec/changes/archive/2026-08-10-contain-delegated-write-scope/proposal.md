# Change: Contain delegated write-capable subagent scope to its assigned worktree

## Why

The platform's multi-agent lifecycle already isolates ordinary task work into git worktrees (`start_task.py` / `start_worktree.py`) and blocks direct commits/merges in the integration copy via `scripts/git_hooks/pre-commit` and `pre-merge-commit`. Those hooks stop a human or agent from running `git commit`/`git merge` directly in the integration copy, but nothing today verifies that a write-capable subagent delegated to work in one worktree did not also write files into `integration/main` (or another worktree) through some other path — a stray absolute-path `Write`/`Edit` call, a `Bash` command that `cd`s out of the assigned directory, or a delegated agent that silently changes cwd. If that happens today, it can go unnoticed until someone runs `git status` in the integration copy and finds unexplained changes mixed with their own in-progress work.

This is explicitly out of scope for the `stabilize-merge-lifecycle` change (see its proposal's "Out of scope" and design.md's "Known follow-up boundary"), which only covers the GitHub-facing merge lifecycle, not delegated-agent filesystem containment.

## What changes

- Define a `delegated_write_containment` contract: every write-capable delegation carries an absolute `assigned_worktree`, a pre-delegation snapshot of `integration/main`'s state is captured, and a post-delegation comparison against that snapshot detects any change that landed outside the assigned worktree.
- Where the calling platform controls subprocess/subagent launch, run it with `cwd=assigned_worktree`. Document this as a partial mitigation, not enforcement — a subprocess can still `cd` away or use absolute paths.
- Where the underlying agent runtime exposes a real pre-write enforcement point (see design.md for what Claude Code and Codex actually expose today), document how to wire assigned-worktree scoping into it. Where no such enforcement point exists, the contract is detection plus fail-closed, not prevention.
- On containment violation: fail closed (do not proceed as if delegation succeeded), never automatically `stash`/`reset`/delete anything in `integration/main` (that could be someone else's legitimate in-progress work), and produce a message that names the specific out-of-scope path(s).
- Distinguish pre-existing dirty state in `integration/main` (already present in the pre-delegation snapshot) from new changes introduced during delegation; only the latter is a containment violation.
- Record a friction event through the existing `agent_friction.py` mechanism, but only after the safe (non-mutating) comparison has run — never before, and never in a way that itself requires GitHub auth (the incident must be recorded locally even when GitHub is unreachable).

## Out of scope

- Any change to the already-verified `stabilize-merge-lifecycle` GitHub-merge contract.
- A general-purpose filesystem sandbox for Claude Code (no such native primitive exists today; see design.md).
- Automatically repairing or reverting a detected containment violation. This change detects and reports; a human decides remediation.
