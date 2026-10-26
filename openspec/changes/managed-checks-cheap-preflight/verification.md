OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the completion-lifecycle delta, proposal, design and tasks; dogfood run of the new preflight on this task; targeted tests; repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope decision

Slice 1 of Requirement BR-773. The split into small children is a technical decision of the backlog-revision session (2026-10-26), not an owner decision. Evidence reuse across `archive`/`finish`, refusing a repeated run of identical content and the private-reference guard in `select_checks` stay for a later child.

## Execution

Route `standard`, plan `supervisor-retained` (`balanced-parent`); the supervisor implemented the change and recorded `record-retained-execution`. During implementation the scope was narrowed in the artifacts first: the refusals apply only while the managed change is active, because portable `finish` runs `select_checks --execute` without `--evidence` after archive.

## Completeness

- Managed run without evidence: `test_active_managed_change_without_evidence_is_refused_before_any_command` (no `DEV_PLATFORM_CHECK_COMMAND`, message names the evidence path). Dogfood: `select_checks --execute` without `--evidence` on this task stopped before any command with the same message.
- Last task checkbox still open: `test_open_task_checkbox_is_refused_before_any_command` (names "1 of 2 task(s) remain incomplete", no command started).
- Archive-ready proceeds / archived keeps the existing path: `test_archive_ready_or_archived_change_passes_the_preflight`; the full run on this task passed through the preflight.
- Stale manifest before the full test run: `test_platform_full_set_checks_the_manifest_before_the_full_test_run`; the evidence shows the manifest check executed before `run_test_groups.py --all`.
- A portable-finish fixture created a new capability without `## Purpose`; the preflight correctly refused it, and the fixture now carries a Purpose.

All tasks in `tasks.md` are complete.

## Correctness and coherence

`require_active_change_ready` reuses `openspec_lifecycle.archive_content_problems`, so the preflight and archive cannot disagree. Required checks are unchanged (BR exclusion); only their order changed. `docs/engineering/agent-workflow.md` describes the preflight.

Pre-existing fallback noticed, not changed: `select_checks` continues with the full set when the affected-test precheck is "unavailable".

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence ...` on head 127eeb90 (contains origin/main 6982017f) passed: compileall, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all` (1217 s). An earlier run on 99c5fc79 stopped in the affected precheck (the Purpose-less fixture above); a rerun on 127eeb90 was killed by a machine reboot before completing.
