# Proposal: Activate exact-head project harness migration before CLI execution

## Why

The `v1.4.34` compatibility migration appended replacement definitions after
project-owned scripts' `__main__` guard. Imports can observe the definitions,
but invoking either script executes the legacy `main()` first. That leaves the
stale-branch vulnerability active for real Jara and Planner CLI runs.

## What changes

- Replace append-after-entrypoint migration with a reviewed deterministic
  transformation that installs the exact-head implementation before the
  original script's CLI guard.
- Execute migrated Jara-like and Planner-like fixtures as real CLIs, including
  stale historical merged PR / reused-branch regressions.
- Preserve project-owned lifecycle entrypoints and fail closed on unknown bytes.
- Release a patch and dispatch the standard reviewed superseding rollout.

## Non-goals

- Do not manually edit or merge the existing downstream rollout PRs.
- Do not change Cuby's platform-owned harness contract.
