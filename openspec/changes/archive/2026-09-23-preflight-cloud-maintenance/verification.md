# Verification: cloud maintenance setup preflight

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active delta against the enabled workflow inventory, Actions secret metadata, dedicated provider probe, documentation, and tests; focused and full automated checks.
Automated-Checks-Evidence: automated-checks.json

The operator command reads the enabled states of the three cloud workflows and repository secret names. Missing `OPENAI_API_KEY` is reported before any workflow dispatch. The dedicated Actions probe uses the secret only inside the job, discards the provider response body, and emits fixed status categories. Disabled cloud maintenance remains separate from deterministic CI, release, and rollout. No secret value or second state store is written.

Executed before archive:

- `python3 -m unittest tests.test_cloud_maintenance_preflight -q` — 6 passed, including a mocked 401 response that emits no credential.
- `python3 scripts/run_test_groups.py --verify-coverage` — 1,232 discovered tests matched the declared mandatory groups.
- `python3 scripts/cloud_maintenance_preflight.py --repo lehard/dev-platform --ref main` — exited 2, reported the currently missing `OPENAI_API_KEY` name, and dispatched no probe. Provider authentication could not be checked until an operator configures that secret and the probe workflow reaches `main`.
- `openspec validate preflight-cloud-maintenance --strict --no-interactive` — passed.
- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/preflight-cloud-maintenance/automated-checks.json` — compileall, Ruff, and all mandatory test groups passed.
