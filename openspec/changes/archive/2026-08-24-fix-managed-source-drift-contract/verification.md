# Verification: Fix managed source-drift contract

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review against `proposal.md`, `design.md`, and both delta specs; structural OpenSpec validation; focused managed-lifecycle tests; and the platform's complete declared regression suite.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The implementation removes only deterministic authoring-receipt material from newly calculated source-Issue content hashes, while title and other body edits still change the evidence and block pre-materialization start.
- Legacy packages remain compatible through the original raw-hash comparison; packages that lack evidence continue to skip the guard.
- The central `dogfood_task.py status` entrypoint now accepts and forwards `--json`, matching its own source-drift diagnostic and preserving the bounded hashes emitted by `finish_task.py`.
- The active change stays scoped to managed-task intake/status behavior. It neither rewrites materialized OpenSpec from a later Issue edit nor changes publication, routing, or source-Issue authority.
- Central and rendered-template documentation describe the same normalization and recovery surface.

## Checks run

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 -m unittest tests.test_managed_task tests.test_central_dogfood_lifecycle tests.test_managed_status_lifecycle`
- `python3 scripts/run_test_groups.py --all` — 13 groups / 720 declared tests, all passed.
- `openspec validate fix-managed-source-drift-contract --strict`
- `python3 template/scripts/openspec_lifecycle.py check`
- `git diff --check`
