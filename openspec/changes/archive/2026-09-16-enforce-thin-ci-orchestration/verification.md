# Verification: enforce-thin-ci-orchestration

OpenSpec-Verify: PASS
Verification-Method: Reviewed the materialized delta against the accepted Platform CI and agent-instruction specs, inspected both central and rendered workflows, and ran targeted plus full automated validation.
Automated-Checks-Evidence: automated-checks.json

Checks completed before archive:

- `python3 -m compileall -q template/scripts scripts`
- `python3 -m unittest tests.test_agent_instruction_architecture tests.test_template_contract` (45 tests)
- `python3 scripts/managed_projects.py validate`
- `python3 scripts/run_test_groups.py --all` (864 tests across 13 groups)
- `python3 template/scripts/openspec_lifecycle.py check`
- `npx --yes @fission-ai/openspec@1.6.0 validate --all --strict --no-interactive`

The archive helper will run selected applicable checks and write their machine-readable evidence to `automated-checks.json`.
