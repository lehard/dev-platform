# Verification: Isolate managed intake from project-owned publication APIs

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) against proposal/design/delta spec, plus the full local platform test and validation matrix
Automated-Checks-Evidence: automated-checks.json

## Automated validation

Run from the task worktree on branch `agent/isolate-managed-intake-project-harness`, reconciled onto `origin/main` `80c84afd9c44e93950152394c7746ceaa2136eda` with normal Git history:

- `python3 -m compileall -q template/scripts scripts tests` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — `outcome: "success"`, 13/13 groups, `failed_groups: []`; coverage `declared_test_count == discovered_test_count == 843`, `missing_from_groups: []`, `duplicated_tests: []`
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`
- `openspec validate isolate-managed-intake-project-harness --strict` — valid
- `python3 scripts/check_docs_links.py` — no problems
- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/isolate-managed-intake-project-harness/automated-checks.json` — `high-impact-path`, selection `ready`, 3/3 selected commands `success` (see automated-checks.json)

New regression coverage:

- `tests/test_managed_intake_project_harness_isolation.py`
  - `test_standard_start_import_graph_loads_without_platform_publication_api` — builds a scripts/ directory with the platform-owned managed-start import graph plus a Jara-shaped `project_publish.py` / `finish_task.py` that expose neither `PrRef` nor `request_protected_merge` / `sync_after_remote_pr_merge`, then runs `python -c "import start_task, rollout_preflight"` in a subprocess and asserts exit 0.
  - `test_read_only_observation_works_against_the_project_harness_fixture` — against the same fixture, `observe_pending_rollout` returns `NONE` and `reconcile_pending_rollout` with a `harness_mode=project` config returns `NONE` with a `harness_mode=project` diagnostic, importing no publication module.
  - `test_rollout_preflight_has_no_toplevel_project_owned_publication_import` — static AST guard: `rollout_preflight.py` has no module-level `import` / `from` of `project_publish` or `finish_task`.
- `tests/test_rollout_preflight.py` (`HarnessModeGateTests`)
  - `test_project_harness_skips_platform_reconciliation_without_observing` — `harness_mode=project` short-circuits to `NONE` without calling `observe_pending_rollout` or any merge.
  - `test_platform_harness_missing_publication_helper_fails_closed_before_merge` — a `PlatformPublicationUnavailable` from the lazy loader is translated to `BLOCKED` (PR retained) with no `_merge_rollout_pr` / `_synchronize_local_main` call.
  - `test_loader_reports_every_missing_platform_dependency` — with `project_publish` and `finish_task` imports denied, `_load_platform_reconciliation_helpers` raises naming both `scripts/project_publish.py:request_protected_merge` and `scripts/finish_task.py:sync_after_remote_pr_merge`.
  - `test_loader_populates_real_helpers_when_platform_modules_are_present` — in a normal platform checkout the loader binds both callables.

The existing platform-harness `ReconcilePendingRolloutTests` (green merge → `RECONCILED`, changed / conflicting head → `BLOCKED`, accepted-but-head-changed `SystemExit` → `BLOCKED`, merged-but-sync-failed → `MERGED_NEEDS_LOCAL_SYNC`) are retained unchanged and pass; `_merge_rollout_pr` still forwards `pr.head_sha` as `expected_head`, and `request_protected_merge`'s `--match-head-commit` exact-head guard (covered by `test_publication_recovery_cli.py`) is untouched.

## Semantic review

Completeness: PASS.

- Delta requirement "Managed start is independent of project-owned publication APIs":
  - Scenario "Jara-shaped project harness lacks a platform publication type" — `rollout_preflight.py`'s module-level imports are now platform-owned only (`_platform_common`, `integration_state`, `publication_state`, `rollout_identity`). `PrRef` was moved to `publication_state.py` (rendered for every harness, never in `_skip_if_exists`) and `project_publish.py` re-exports it. `serialized_integration` is imported from its defining module `integration_state` instead of via the `finish_task` re-export. Proven by the subprocess fixture and the AST guard above.
  - Scenario "Platform-only publication dependency is unavailable" — `reconcile_pending_rollout` calls `_load_platform_reconciliation_helpers()` only after it has confirmed `harness_mode=platform` and an unambiguously green (`SAFE_TO_ADOPT`) rollout. A missing platform-owned module raises `PlatformPublicationUnavailable`, caught and returned as `BLOCKED` before `_merge_rollout_pr` / `_synchronize_local_main` — i.e. before any GitHub merge, integration-branch sync, worktree, board, or Project-status write. Because `reconcile_pending_rollout` runs inside `start_task.start_task()` ahead of `create_worktree` / board admission / `managed_project_status.reconcile`, a `BLOCKED` result raises in `start_task` with no partial lifecycle mutation.
- Delta requirement "Project-harness compatibility coverage exercises the standard entrypoint" — `test_managed_intake_project_harness_isolation.py` preserves a project-owned `project_publish.py` whose exports differ from the platform harness and exercises the real `import start_task` entrypoint (not an isolated helper or a project recovery command); the AST guard fails closed if a load-time edge is reintroduced; platform-harness exact-head `ReconcilePendingRolloutTests` remain green.

Correctness: PASS.

- `PrRef` moved verbatim: same fields (`number: int | None`, `url: str`, `already_merged: bool = False`) and the same `ref` property raising the identical `SystemExit` on an unstable reference. `_pr_ref` in `project_publish.py` and every external importer (`project_publish.PrRef` in `test_managed_status_lifecycle.py`, `test_pr_reconciliation_concurrency.py`, `test_publication_recovery_cli.py`) resolve through the re-export; `rollout_preflight.PrRef is project_publish.PrRef is publication_state.PrRef` is `True`.
- No test fixture that copies `project_publish.py` needed editing: `test_git_lifecycle.py`, `test_publication_recovery_cli.py`, `test_merge_lifecycle_resilience.py`, and `test_protected_main_zero_handoff.py` already copy `publication_state.py` into their synthetic scripts/ directory, so `from publication_state import PrRef` resolves there.
- The lazy loader reassigns only module globals that are still `None`, so `patch.object(rollout_preflight, "request_protected_merge", …)` / `"sync_after_remote_pr_merge"` in existing tests continue to work (the attributes exist, initialised to `None`), and a test that patches them makes the loader a no-op.
- The `harness_mode` gate uses `_platform_common.harness_mode`, which defaults to `"platform"` for legacy configs, so platform-harness behaviour and every existing `CONFIG`-based test are unchanged.
- `observe_pending_rollout` (read-only, used by `agent_doctor.py` for all harness modes) is unchanged in behaviour; only its docstring was updated to describe the new self-gating.

Coherence: PASS.

- Changes are confined to `template/scripts/{publication_state,project_publish,rollout_preflight}.py`, their tests, and a single new test-group line in the platform-internal `dev-platform/checks.toml`. `template/dev-platform/checks.toml` (downstream) is untouched — the new test is platform-internal.
- No new CLI flags, commands, or user-facing surfaces; `docs/engineering/*` entrypoint descriptions stay accurate (`check_docs_links.py` clean).
- `platform_doctor.TASK_START_DEPENDENCY_MODULES` already lists `rollout_preflight` and needs no change; the task-start probe still imports it (now with fewer transitive modules).
- No change to release refs, the rollout registry, provider-local routing, the platform-harness exact-head rollout guard, branch protection, worktree isolation, or the `harness_mode=project` project-owned lifecycle.

## Scope boundary

Per the accepted change boundary: no project-owned Jara lifecycle code was replaced with template code, no financial/product code was touched, and no branch-protection / exact-head-publication / worktree-isolation / Project-status gate was weakened. Downstream Backlog #93 / #100 are not retroactively closed or transitioned. Archive and publication are performed through the managed lifecycle helper.
