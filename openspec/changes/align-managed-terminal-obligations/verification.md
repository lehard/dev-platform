# Verification: managed terminal obligations

OpenSpec-Verify: PASS
Verification-Method: Manual scenario-by-scenario review of the accepted Requirement, active OpenSpec delta, implementation, and regression assertions; strict OpenSpec validation and platform checks.
Automated-Checks-Evidence: automated-checks.json

The exact PR merge fact remains sourced from publication observation. Read-only status checks Project Done, linked process evidence, and exact deferred cleanup before claiming full completion. A missing linked Issue leaves both status and finish pending; an explicit disposition requires repository access, an HTTP 404 response, a bounded reason on the managed source Issue, and comment read-back. Authentication and permission failures cannot create a disposition. The tests cover merged-but-pending status, cleanup pending versus exact deferred warning, finish blocking and disposition, and rejected 403.

Checks completed before archive:

- `python3 -m unittest tests.test_managed_task tests.test_managed_status_lifecycle` — 111 passed after the final test addition.
- `python3 scripts/select_checks.py --base origin/main --execute` — compileall, Ruff, and all platform test groups passed before the final test-only addition.
- `python3 -m ruff check template/scripts/finish_task.py template/scripts/managed_task.py tests/test_managed_task.py tests/test_managed_status_lifecycle.py` — passed after the final test addition.
- `python3 scripts/managed_projects.py validate` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- `openspec validate align-managed-terminal-obligations --strict` — passed.
- A read-only `gh api -i` probe against a nonexistent Issue confirmed that GitHub CLI exposes an HTTP 404 status line in stdout for the disposition gate.

The archive helper will run its required checks and generate the exact automated evidence before archiving. No test failure was classified as pre-existing.
