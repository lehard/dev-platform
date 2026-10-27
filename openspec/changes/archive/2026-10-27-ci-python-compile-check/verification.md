OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review of scripts/check_ci_python.py, dev-platform/checks.toml, AGENTS.md, docs and the new test module against the platform-ci delta, proposal, design and tasks; a direct run of the check on this repository (local 3.13, CI 3.11, compiled on python3.11) and on a reproduction of the earlier 3.11-only defect (21 context managers in one `with`: exit 1 naming both versions and "too many statically nested blocks"); repository-owned selected checks (full set, including the new step) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope

Developer validation detects a Python-minor mismatch with CI before handoff (coordinator decision, variant C). Changed: new `scripts/check_ci_python.py`, `dev-platform/checks.toml` (full and Python command sets, evidence types, test group), `AGENTS.md` and `docs/engineering/agent-workflow.md` validation lists, new `tests/test_check_ci_python.py`.

## Limit

The step detects compile-time errors only. Runtime behaviour differences between the local Python version and the CI version are not caught by it; required CI on the exact PR head remains the merge gate.

## Completeness

- The CI version is read from the single `actions/setup-python` step of job `validate` in `.github/workflows/ci.yml`, never hard-coded (`test_repository_ci_workflow_pins_a_readable_version`).
- Scenario "Compile error only on the CI version": `test_ci_only_compile_error_fails_naming_both_versions` (exit 1, "local 3.13 but not on CI 3.11", compiler output); reproduced for real against python3.11 with the nested-block defect.
- Scenario "CI-version interpreter is missing": `test_missing_or_wrong_ci_interpreter_is_refused_naming_both_versions` (exit 2 "local 3.13, CI 3.11: no python3.11 on PATH"; an interpreter reporting 3.12 is refused too).
- Unreadable CI version (missing workflow, no or two setup-python steps, a non `major.minor` value) is refused with exit 2 naming the local version: `test_unreadable_ci_version_is_refused_naming_the_local_version`.
- Scenario "Matching versions": `test_matching_version_passes_without_a_second_compilation` and the CLI test.
- Wiring: `test_full_check_set_runs_the_step`; the full selected-check run below executed the step (local 3.13, compiled on python3.11).
- No fallback: no default version, interpreter or skip; every unreadable or unavailable input is exit 2.

All tasks in `tasks.md` are complete.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/ci-python-compile-check/automated-checks.json` on head d4381961 passed: affected precheck, compileall, `check_ci_python.py`, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all`.
