# Proposal: Preserve independent start with a degraded agent board

## Why

A machine-local multi-agent board can contain an entry whose worktree/branch identity is no longer provable, or whose task is already terminal. That entry is not a trustworthy active file claim. A separate task with no proven concrete-file conflict must remain able to start in its own worktree; otherwise unrelated cleanup debt serializes the whole repository.

The current implementation excludes non-valid entries from admission and allows that parallel start. However, agent-doctor reports the same condition as a generic warning and the contract lacks an explicit regression for managed start. Operators can reasonably mistake the warning for a fatal gate. This change makes the existing safety boundary explicit and durable across the Copier-managed platform surface.

## What Changes

- Specify that only a valid, active board identity with proven concrete-file claims can block multi-agent admission.
- Preserve non-blocking diagnostics for degraded or terminal sibling entries, and make start output distinguish those warnings from an actual `WAIT`/blocked result and a successful materialization.
- Add controlled lifecycle coverage for independent managed start despite a branch/path-mismatched or terminal sibling record, and for continued blocking of a valid same-file claim.
- Render the behavior and operator guidance through the platform template so fresh and upgraded platform-owned managed projects receive the same contract.

## Non-Goals

- Automatically repair, remove, reset, stash, merge or take ownership of another task's worktree, branch or board entry.
- Treat a malformed entry as safe evidence that a same-file overlap is intentional.
- Weaken valid active scope-claim admission, cross-machine coordination limits, or `harness_mode=project` ownership.
- Auto-merge rollout PRs or write directly to downstream default branches.

## Impact

- Affected specifications: `worktree-coordination`, `platform-lifecycle` documentation.
- Affected surfaces: `agent_board.py`, agent-doctor/start lifecycle diagnostics, managed-start regression fixtures, template rendering and Copier upgrade smoke coverage.
- Downstream delivery: immutable platform release followed by normal managed rollout PRs.
