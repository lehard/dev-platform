## Why

Since 2026-10-28 a release opens no rollout PR; a project is updated on request through the targeted Roll Out Platform. An audit found mechanisms that only served automatic rollout or long-unsupported versions.

## Inventory (checked on main 69c8d093 against the managed registry)

| Item | Evidence | Decision |
| --- | --- | --- |
| `.github/workflows/reconcile-stale-rollouts.yml` daily cron `23 4 * * *` | No automatic rollout PRs are created; stale PRs can still come from manual rollouts, so the maintenance stays available. The same schedule also runs the rollout-alert recovery check (BR-832 territory, excluded) | stale-rollout plan/apply only on `workflow_dispatch`; the schedule keeps only the alert recovery check |
| Legacy-harness exact-head migration in `scripts/rollout_project.py` (`LEGACY_*` fingerprints and overrides, v1.4.34 append recovery, `migrate_project_publication_safety`, `apply_operator_legacy_harness_continuity`) | Registry projects record `_commit` v1.6.0 (planner-agent-lab, Jara_Fin, cuby), v1.8.2 (ai_assist_content), v1.10.0 (ilrai-crm-workbench), v2.0.0 (terrazzo_mvp, agent-control-room): none is before 1.4.35; the operator configuration carries no `[rollout.legacy_harness_migrations]`, so the code is inert | remove code, its operator-config section, docs and tests; the exact-head conformance gate for `harness_mode=project` stays |
| `--defer-rollout` / `DEV_PLATFORM_DEFER_ROLLOUT` | A manual targeted rollout still opens a rollout PR in the project, which task start merges; the deferral still protects a session from that merge | keep; not proven unneeded |
| `docs/managed-rollout.md` "eligible for automatic rollout PRs" | Contradicts the manual-only rollout | rewrite to the manual targeted rollout |

## What Changes

- Stale-rollout reconciliation (dry-run plan and apply) runs only on explicit dispatch; the scheduled run keeps only the rollout-alert recovery check.
- The legacy-harness migration and its configuration are removed; a project-owned harness that does not prove exact-head conformance fails rollout closed as before.
- Rollout documentation describes the manual targeted rollout.

## Impact

- `.github/workflows/reconcile-stale-rollouts.yml`, `scripts/rollout_project.py`, `tests/test_rollout_recopy.py` (and any test tied to the removed items), `docs/managed-rollout.md`, `docs/public-cutover.md`, `docs/operator-config.example.toml`, `docs/engineering/code-erosion.md` if it references the removed code.
- Specs: platform-rollout (two legacy-migration requirements removed, the conformance requirement and stale-rollout maintenance modified), platform-config (operator handoff no longer lists legacy migration values).
- Not template-visible: no file under `template/` changes, so new renders and Copier updates of existing projects are unaffected.
