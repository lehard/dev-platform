# Verification: managed terminal reconciliation

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic review (completeness, correctness, coherence) plus targeted terminal-reconciliation tests and the complete platform test matrix.
Automated-Checks-Evidence: automated-checks.json

## Completeness

- The recognized Planner migration requires both reviewed project-publish and
  finish-task surfaces, installs the exact-head and terminal helpers, and
  rejects unknown bytes before rollout mutation.
- The helper only acts after an exact GitHub merged-head proof, reconciles the
  bound Project item to `Done`, and closes the same source Issue.

## Correctness

- Focused tests prove no terminal mutation before exact merge, successful
  `Done` plus Issue closure, and a truthful error after temporary Issue-mutation
  failure.
- Rollout tests prove recognized migration is idempotent and preserves the
  standalone-clone entrypoint; existing delayed-check recovery coverage passes.

## Coherence

- The migration retains `harness_mode=project` ownership and uses no new PR or
  implementation path on retry.
- Unknown project harness content remains fail-closed and unmodified.

## Automated evidence

- `python3 -m pytest tests/test_project_terminal_reconciliation.py tests/test_rollout_recopy.py tests/test_managed_status_lifecycle.py -q` — 55 passed.
- `python3 scripts/run_test_groups.py --all` — 677 tests across 13 groups passed.
