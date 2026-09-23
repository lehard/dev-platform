# Tasks

## 1. Specify the validation ownership boundary

- [x] Update the managed-rollout OpenSpec delta so rollout preparation validates Harness installation/compatibility and downstream PR CI validates product behavior for both harness modes.

## 2. Implement the shared rollout change

- [x] Remove selector/product-command execution from `run_project_validation()` without changing the existing reject, diff, or doctor gates.
- [x] Emit concise rollout output that product verification is delegated to downstream CI.

## 3. Verify and document

- [x] Update focused rollout validation tests to assert both modes retain Harness checks and neither invokes `select_checks.py`.
- [x] Run focused tests, source/template validation, full platform test groups, and semantic OpenSpec verification; record truthful evidence.
- [x] Validate template rendering/updated-project behavior through the repository's existing test coverage and retain the downstream rollout-PR CI boundary.

## Logical commits

- [x] Commit the OpenSpec contract, implementation, tests, and guidance together because they jointly define one observable rollout validation boundary.
