OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-rollout and platform-config deltas, proposal, design and tasks; registry evidence read from each registered repository's committed `.copier-answers.yml` on 2026-10-30; targeted tests of every test module referencing the changed files; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Registry evidence (2026-10-30)

`_commit` in `.copier-answers.yml`: lehard/planner-agent-lab v1.6.0 (excluded), lehard/Jara_Fin v1.6.0, lehard/cuby v1.6.0 (excluded), lehard/terrazzo_mvp v2.0.0, kamenkadmitry/ai_assist_content v1.8.2 (excluded), lehard/agent-control-room v2.0.0, lehard/ilrai-crm-workbench v1.10.0. None is before 1.4.35. The installation's operator configuration has no `[rollout.legacy_harness_migrations]`, so the removed migration was inert.

## Decisions

- Removed: the legacy-harness exact-head migration (`LEGACY_*` fingerprints and overrides, v1.4.34 append recovery, legacy test-surface migration, CLI-guard override installer, `_read_operator_config`, `apply_operator_legacy_harness_continuity`, `migrate_project_publication_safety`) and its operator configuration and docs. Kept: `require_project_publication_safety_conformance` (fail-closed gate) and the pre-cutover `legacy_repository` tag bridge (a different feature).
- Stale-rollout reconciliation (plan and apply) runs only on `workflow_dispatch`; the schedule stays only for the rollout-alert recovery step, which belongs to the excluded alarm path (BR-832).
- Kept with evidence: `--defer-rollout` / `DEV_PLATFORM_DEFER_ROLLOUT` — a manual targeted rollout still opens a rollout PR in the project that task start merges, so the session deferral still applies; its code lives in stream-A files that stay untouched.
- Spec: the conformance requirement is replaced (REMOVED + ADDED under a new name) because the validator does not allow dropping scenarios through MODIFIED; the two legacy-migration requirements are REMOVED; platform-config operator handoff no longer lists legacy migration values.

## Completeness

- Workflow: `test_stale_rollout_reconciliation_runs_only_on_operator_dispatch`; existing workflow tests (`test_rollout_failure_streak_workflow`, `test_ci_guardrails`, `test_managed_rollout`, `test_rollout_control_plane_regressions`) pass.
- Migration removal: legacy migration tests deleted from `tests/test_rollout_recopy.py`; conformance tests (`test_project_publication_conformance_*`) and the legacy baseline bridge tests pass.
- Docs: `docs/managed-rollout.md` describes manual targeted rollout (`## Release rollout`, `## Manual retry`) and no longer promises automatic rollout PRs; the legacy continuity section, `docs/operator-config.example.toml` table and `docs/public-cutover.md` checklist item are removed. Explorer nodes bound to the renamed heading are rebound and marked reviewed.
- Template: no file under `template/` changes except the regenerated manifest, so new renders and Copier updates are unaffected.

## Not verified / limits

- `docs/decisions/0005-managed-rollout-on-demand.md` is a dated decision record and is unchanged.
- Independent review round 1: material `unused-ast-import` fixed (`import ast` removed; ruff's configured rule set did not flag it); advisory: `docs/engineering/code-erosion.md` baseline now notes the hotspot function was removed after that measurement.
- Independent review round 2: material `terminal-reconciliation-requirement-left-stale` fixed — "Project-harness rollout proves terminal reconciliation conformance" is replaced by a no-rewrite version (the gate still requires the terminal-reconciliation signals when `scripts/finish_task.py` exists, covered by the existing conformance tests). Advisories accepted: the generic "Public rollout core contains no private-project compatibility branches" and "Removing private compatibility does not silently break the operator fleet" requirements stay (this change is their "compatibility can be removed / no current dependency remains" case); the "on this installation" sentence in `docs/managed-rollout.md` states the current operator setting; the scheduled run still mints the target token because the alert recovery step needs it.
- Independent review round 3: ready (advisories only, listed in the review files).
