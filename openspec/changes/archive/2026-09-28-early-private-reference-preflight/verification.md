# Verification: early private-reference preflight

OpenSpec-Verify: PASS
Verification-Method: Manual scenario-by-scenario review of the active delta, implementation, and regression assertions; strict OpenSpec validation and platform checks.
Automated-Checks-Evidence: automated-checks.json

The completion preflight calls the existing source-owned guard before `run_checks`. The guard classifies candidate file content, candidate paths, branch name, new commit messages, and proposed PR text without printing private identifiers or filenames. Its diagnostic points to the managed task's opaque private-lineage handle. The publication recheck remains in `finish_task.py`, and `project_publish.py` retains its existing fail-closed guard.

Checks completed before archive:

- `python3 -m unittest tests.test_private_backlog_guard tests.test_git_lifecycle tests.test_template_contract` — 71 passed before the final diagnostic wording adjustment.
- `python3 -m unittest tests.test_private_backlog_guard tests.test_git_lifecycle.GitLifecycleTests.test_private_reference_preflight_blocks_evidence_and_commit_before_validation` — 5 passed after that adjustment.
- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `python3 scripts/run_test_groups.py --all --quiet` — all 13 groups passed, 1399 tests discovered with complete group coverage.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- `openspec validate early-private-reference-preflight --strict` — passed.
- `git diff --check` — passed.

An earlier full test run failed only in template render tests because local Copier 9.17.1 was below the template's declared minimum 9.18.2. After updating Copier to 9.18.2, the failing group and the full suite passed. No product test failure remains.

The archive helper will run required selected checks and generate the exact automated evidence before archiving.
