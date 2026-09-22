# Verification: Separate rollout Harness validation from product verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active OpenSpec contract, implementation, tests, and rollout guidance, backed by the recorded automated checks below.
Automated-Checks-Evidence: automated-checks.json

## Method

Performed a manual semantic review of `proposal.md`, `design.md`, the managed-rollout spec delta, implementation, tests, and operator guidance. The change has one boundary: rollout preparation validates the rendered Dev Platform Harness, while the downstream rollout pull request's ordinary CI validates repository product behavior.

## Scenario review

- **Platform-owned Harness:** `run_project_validation()` retains reject detection, `git diff --check`, and `platform_doctor.py`, while the focused test proves it does not invoke `select_checks.py`.
- **Project-owned Harness:** the same focused test covers `harness_mode=project`; a selector file that would fail if executed is present, yet only the diff and doctor commands are called.
- **Different selector CLI and control-plane-selected product commands:** the implementation no longer reads or invokes the selector in either mode, so its CLI and selected commands cannot affect rollout preparation.
- **Harness integrity failure:** reject, diff-hygiene, and doctor gates remain in their original order and continue to fail before rollout publication; only product-command execution was removed.

## Tests and checks run

```text
python3 -m unittest discover -s tests -p 'test_rollout_validation_ownership.py' -v
# 1 test passed; both Harness modes exercise the retained gates and deferred product verification.

python3 -m unittest discover -s tests -p 'test_managed_rollout.py' -v
# 24 tests passed.

python3 -m compileall -q template/scripts scripts
# passed

python3 scripts/managed_projects.py validate
# Managed project registry: OK (3 managed, 0 candidate, 0 excluded)

python3 scripts/run_test_groups.py --all
# 13/13 groups passed; 1,144 discovered tests; no failed groups.

openspec validate separate-rollout-product-validation --strict
# Change 'separate-rollout-product-validation' is valid

python3 template/scripts/openspec_lifecycle.py check
# OpenSpec lifecycle hygiene: OK
```

The full platform suite includes the repository's template/rendering and updated-project coverage. The direct ownership test creates a rendered-project-shaped fixture for both Harness modes and verifies the exact validation command sequence, while `test_managed_rollout.py` retains rollout workflow and release-contract coverage.
