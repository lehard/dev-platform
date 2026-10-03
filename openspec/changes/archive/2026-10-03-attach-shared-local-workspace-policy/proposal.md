## Why
Existing permission safeguards cover platform state but exclude source files. The Mac-local operator adapter applies only to the central checkout, leaving downstream projects to repeat manual owner repair.

## What Changes
- Add an opt-in portable local workspace policy runtime, external registry and idempotent fleet synchronizer.
- Compose permission hooks with existing hooks and retain doctor-managed protections.
- Audit allowed source files before and after supported lifecycle commands; preserve group inheritance and repair only current-user owned paths.
- Add per-user macOS LaunchAgent automation and a cooperative command launcher, discovering only registered repositories under reviewed workspace roots.

## Outcome and Acceptance
Registered checkouts attach automatically, existing hooks keep their exit semantics, restrictive or atomic writes are detected/repaired by the owner, unrelated repositories and foreign active worktrees are unchanged. Verify two disposable identities where available, plus concrete installation on the available Mac projects. Record unavailable second-user execution truthfully.

## Non-goals
No sudo, global Git hooks, blanket permission widening, secrets/cache traversal, foreign task takeover or replacement of the platform Git permission contract.

## Impact
Portable template scripts and lifecycle opt-in, operator installation/runbook, tests and shared-workspace spec. Mac paths/users stay outside tracked public files. Existing projects can attach the external runtime immediately; updated lifecycle integration arrives through reviewed Copier rollout.
