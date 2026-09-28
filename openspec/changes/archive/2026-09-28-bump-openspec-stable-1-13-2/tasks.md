# Tasks: OpenSpec stable version bump (1.13.0 -> 1.13.2)

## 1. Confirm upstream

- [x] 1.1 Re-confirm immediately before editing that `1.13.2` is the current stable OpenSpec release on npm `latest` and the GitHub "Latest" release, with no newer stable.

## 2. Pin bump

- [x] 2.1 Update `template/.dev-platform.toml.jinja` `[tools.openspec]` `min_version`/`tested_version` to `1.13.2`.
- [x] 2.2 Update `.github/workflows/ci.yml`, `.github/workflows/adopt-project.yml` and `template/.github/workflows/dev-platform.yml.jinja` OpenSpec installs/commands to `1.13.2`.
- [x] 2.3 Update `README.md` tested-version prose and `tests/test_template_contract.py` / `tests/project_harness_adoption_smoke.py` assertions to `1.13.2`.

## 3. Focused regressions

- [x] 3.1 Extend `tests/openspec_1_13_regression.py` with case-only duplicate, unpaired `RENAMED`, `RENAMED`+`REMOVED`, task-marker progress and verify-workflow semantics fixtures.
- [x] 3.2 Show the new fixtures fail against exact `1.13.0` and pass against exact `1.13.2`.
- [x] 3.3 Run `validate --all --strict` with `1.13.2` on this repository.

## 4. Validation and receipt

- [x] 4.1 Run compileall, `managed_projects.py validate`, `run_test_groups.py --all` and `openspec_lifecycle.py check`.
- [x] 4.2 Record `verification.md` with the checks actually performed, the platform-guard retention decision, and `OpenSpec-Verify: PASS`.
