# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review of the imported proposal, design, delta spec, implementation, and focused lifecycle tests; confirmed each intent transition, idempotent author/start composition, orphan-provenance block, and ownership-safe Jara_Fin-style migration.
Automated-Checks-Evidence: automated-checks.json

Automated checks run before archive:

- `PYTHONPATH=tests python3 -m unittest tests.test_managed_execution_intake tests.test_template_contract tests.test_managed_rollout tests.test_rollout_validation_ownership tests.test_root_guidance_contract`
- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 scripts/run_test_groups.py --all`
- `git diff --check`

Post-archive CI regression resolution: managed rollout runs the migration before
the rendered bootstrap/doctor. A direct, unreviewed Copier update reports a
missing marker diagnostically until that migration is applied, so the normal
Copier upgrade remains usable without overwriting project-owned guidance. The
exact CI upgrade matrix passed after that adjustment:

- `python3 tests/upgrade_smoke.py --profile light --publish-mode direct`
- `python3 tests/upgrade_smoke.py --profile standard --publish-mode pr`
- `python3 tests/upgrade_smoke.py --profile multi-agent --publish-mode pr`
