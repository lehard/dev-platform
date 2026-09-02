## Why

Managed-task intake is supposed to be dependency-light and reusable across
managed repositories. The Jara_Fin recovery showed that importing the standard
entrypoint can instead require an internal type from project-owned publication
code. A mature downstream project is deliberately allowed to retain that code,
so this turns a platform implementation detail into a hidden start
precondition.

## What Changes

- Separate managed-start and pending-rollout dependencies from project-owned
  publication APIs.
- Define an explicit, platform-owned compatibility boundary for any data or
  operation needed by platform lifecycle code.
- Add a Jara-shaped regression fixture that exercises the actual standard
  managed-start import and admission path.
- Preserve the existing exact-head rollout guard for platform-owned harnesses
  and fail closed without partial lifecycle mutation when the platform-owned
  boundary itself cannot be satisfied.

## Impact

- Affected specifications: `managed-task-intake`.
- Affected implementation areas: the pending-rollout preflight import graph
  (`rollout_preflight.py`), the shared `PrRef` publication cursor
  (`publication_state.py` / `project_publish.py` re-export), and their
  regression tests. The task-start doctor probe already lists
  `rollout_preflight` as a managed-start dependency and needs no change.
- Affected consumers: repositories using `harness_mode=project`, including
  Jara_Fin; platform-owned harness behavior must remain compatible.
