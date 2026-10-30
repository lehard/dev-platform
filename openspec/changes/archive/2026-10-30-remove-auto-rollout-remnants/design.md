## Context

`rollout_project.main()` calls `apply_operator_legacy_harness_continuity()` (reads `[rollout.legacy_harness_migrations]` from operator config into module globals), then per project `migrate_project_publication_safety(project_root, repository)` (rewrites two specific project-owned harnesses selected by repository identity and exact reviewed bytes, including a v1.4.34 append recovery) followed by `require_project_publication_safety_conformance(project_root)` (read-only fail-closed gate for `harness_mode=project`).

## Decisions

- **Remove the migration, keep the gate.** Delete the `LEGACY_*` constants and overrides, `reviewed_legacy_source`, the legacy test-source migration, `_read_operator_config` if it serves only this, `apply_operator_legacy_harness_continuity`, `migrate_project_publication_safety` and their calls; keep `require_project_publication_safety_conformance` and every helper it uses. Helpers used only by the removed code (for example `install_pre_entrypoint_override` and CLI-guard parsing, `EXACT_HEAD_HELPER` if unused) go with it. `ensure_platform_tag_available`'s `legacy_repository` (pre-cutover tag history) is a different feature and stays.
- **Manual-only maintenance.** The supersession step (and its artifact) run only on `workflow_dispatch`; the `schedule` trigger stays for the rollout-alert recovery step, which belongs to the excluded alarm path. Dispatch inputs (dry-run/apply with confirmation) are unchanged.
- **Keep `--defer-rollout`.** It is not automatic-rollout-only (see proposal inventory); it also lives in stream-A files (`start_task.py`), which stay untouched.
- **No fallback.** A project-owned harness without conformance keeps failing rollout closed with the existing diagnostic.

## Risks

- An operator who still had legacy migration values in a private config loses the migration; the registry shows no project needing it, and the conformance gate still blocks an unsafe harness.
