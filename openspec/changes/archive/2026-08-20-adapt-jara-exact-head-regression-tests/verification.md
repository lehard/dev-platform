# Verification: adapt Jara exact-head regression tests

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active proposal, design,
delta specification, reviewed Jara CI failure, implementation, and executable
regression evidence.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

The Jara-only companion adapter accepts the exact known legacy test SHA-256 or
the generated form only when reversing all three exact replacements recreates
that legacy source. All publication harness, helper, and companion-test proofs
finish before any write. The three replacements give strict mocks a local head
and exactly one matching PR record, preserving each original merge fallback,
confirmed-merge, and cleanup assertion. Planner and Cuby never select this
repository-specific path.

## Executed evidence

- Jara #73 failed only three known strict mocks because they rejected
  `git rev-parse` before exact-PR lookup; Planner #46 and Cuby #57 checks are
  green and were not changed.
- `python3 -m unittest tests.test_rollout_recopy -v` — PASS (39 tests),
  including Jara active-harness recovery and unknown/partial no-write cases.
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS.
- `python3 template/scripts/openspec_lifecycle.py check` — PASS.
- `python3 scripts/run_test_groups.py --all` — PASS (674 tests / 13 groups,
  exit 0; aggregate 599.483 seconds).
