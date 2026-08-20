# Proposal: Bind publication to an exact PR head

## Why

A high-severity near-miss in `Jara_Fin` proved that reusing a branch name can make branch-name-only GitHub lookup resolve an older merged PR. That stale PR was accepted as proof for a newer commit and destructive cleanup ran even though the newer commit had not reached `main`.

Dev Platform already requires exact-head publication in its accepted recovery contract, but some implementation paths still re-resolve PRs by branch name. Managed `harness_mode=project` repositories can also carry repository-owned publication code with the same unsafe assumption.

## What Changes

- Make platform-owned PR discovery and all later checks/merge/recovery use one exact publication identity: repository + base branch + head branch + expected head SHA, followed by a stable PR number/URL.
- Require `MERGED` plus exact `headRefOid` confirmation before any destructive cleanup or terminal success.
- Add fail-closed compatibility/conformance handling for managed project-owned harnesses without replacing their repository-specific task/worktree/integration semantics.
- Cover platform-owned, Jara-like, and Planner-like flows with reused-branch regressions.
- Publish an immutable patch release and send the normal reviewed rollout to all managed repositories.

## Impact

This changes engineering-process publication and rollout safety only. Product behavior and application data are unchanged. `harness_mode=project` remains supported and is not converted wholesale to the platform harness.
