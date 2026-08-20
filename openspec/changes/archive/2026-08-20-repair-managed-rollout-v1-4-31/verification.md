# Verification: Repair managed rollout after v1.4.31

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic review plus automated protected-full coverage.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Compared the implementation to both delta specifications. The guarded recopy
  allows only the deterministic, singular marked task-intake block and validates
  protected paths before and after reconciliation; any other protected-path
  mutation remains a failure.
- Confirmed the environment exception is narrow: only
  `GITHUB_ACTIONS=true` with `RUNNER_ENVIRONMENT=github-hosted` changes the
  permission audit to advisory. Local and self-hosted runs retain strict audit
  and repair behavior.
- Confirmed the explicit release PR changes `VERSION` from `1.4.31` to
  `1.4.32`; the existing post-merge workflow is responsible for the immutable
  tag and exact-tag rollout, with no downstream auto-merge.

## Automated checks run

- `python3 -m unittest tests.test_rollout_recopy tests.test_managed_rollout tests.test_platform_doctor tests.test_platform_doctor_workflow_mode tests.test_template_contract` — 87 tests passed.
- `python3 tests/rollout_recopy_smoke.py` — passed.
- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 scripts/run_test_groups.py --all` — protected-full grouped suite passed (660 declared/discovered tests).
- `python3 template/scripts/openspec_lifecycle.py check`
- `git diff --check`
