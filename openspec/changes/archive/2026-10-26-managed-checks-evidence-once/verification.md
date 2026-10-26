OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle and platform-lifecycle deltas, proposal, design and tasks; dogfood of the repeated-run refusal on this task; targeted tests; repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope decision

Slice 2 of Requirement BR-773 (technical split by the backlog-revision session, 2026-10-26). Item "scope-overlap gate covers BR-777" needed no code: `select_checks` calls the board's `enforce_scope_gate`, whose own diff is computed against the observed `origin/<main>` and treats declared generated files as soft (BR-777/T1). The unavailable-precheck behavior was chosen as an explicit stop: 147 archived evidence files show no `unavailable` outcome, so the stop costs nothing in normal operation and removes a silent degraded path.

## Execution

Route `standard`, plan `supervisor-retained`; the supervisor implemented the change and recorded `record-retained-execution`.

## Completeness

- Repeated managed run over unchanged content: `test_reusable_evidence_refuses_a_repeated_run_before_any_command` (no command started, names the evidence and "archive and finish reuse it"). Dogfood: after the green run, `select_checks --execute --evidence openspec/changes/managed-checks-evidence-once/automated-checks.json` on a16b2280 exited 1 with "Repeated selected-check run refused before any command started ... already proves this task content".
- Repeated quick run: `test_reusable_quick_evidence_refuses_a_repeated_run`.
- Content changed / failed evidence: `test_not_reusable_evidence_is_printed_and_the_run_proceeds`; absent evidence: `test_absent_managed_evidence_has_nothing_to_repeat`.
- Archive after a green evidence run: `test_archive_reuses_evidence_that_proves_unchanged_content` (no selected command, `DEV_PLATFORM_CHECK_REUSE` reused). Archive without reusable evidence: `test_archive_runs_checks_when_evidence_is_absent_or_not_reusable`. The existing portable end-to-end archive (`test_portable_archive_completes_real_checks_and_archive`) still runs real checks.
- Private-reference guard before any command: `test_private_reference_guard_stops_before_any_command`.
- Unavailable precheck: `test_unavailable_precheck_stops_before_the_full_set` (exit code kept, or 1 when the runner exited 0; failure evidence, `affected-precheck-unavailable` descriptor, no full command).

All tasks in `tasks.md` are complete.

## Correctness and coherence

Both the refusal and archive reuse call `automated_evidence_reuse` / `quick_evidence_reuse`, i.e. `check_evidence_reuse`, the rule finish uses (BR-785), so the three cannot disagree. Archive decides before calling `select_checks`, finish skips reusable evidence before calling it, and coordinator finalization runs without `--evidence`, so the refusal stops only a manual repeat. A decision error (git, selection) raises. The guard is `private_lineage.require_clean_candidate`, the one archive already runs. Required checks are unchanged (BR exclusion). `docs/engineering/agent-workflow.md` describes the refusal, archive reuse, guard and the unavailable stop.

Pre-existing, not changed: `select_checks` imports `block_for_scope_conflict` with an `ImportError` compatibility stub; finish's `observe_private_reference_blocker` returns no blocker when the guard script is absent.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence ...` on head a16b2280 (contains origin/main 3b7ca769) passed: affected precheck success, compileall, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all` (994 s, after a long machine-pool wait under load).
