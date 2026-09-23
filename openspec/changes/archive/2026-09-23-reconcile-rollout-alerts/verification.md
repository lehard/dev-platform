# Verification: rollout alert reconciliation

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active delta against the issue tracker, project version coherence helper, scheduled workflow, and regression tests; focused and full automated tests.
Automated-Checks-Evidence: automated-checks.json

The reconciliation command reads the existing failure issue and both authoritative version markers on the project's default branch. It closes the issue only after the markers agree at or beyond the last failed release; missing, inconsistent, older, or unreadable state leaves it open. A daily maintenance schedule runs this read and issue update independently of a later rollout or a manual supersession apply. The scheduled path does not apply stale PR changes. No second alert store is introduced.

Executed before archive:

- `python3 -m unittest tests.test_rollout_failure_streak tests.test_rollout_failure_streak_workflow -q` — 27 passed.
- `python3 -m unittest tests.test_ci_guardrails -q` — 5 passed.
- `openspec validate reconcile-rollout-alerts --strict --no-interactive` — passed.
- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/reconcile-rollout-alerts/automated-checks.json` — compileall, Ruff, and all mandatory test groups passed.
