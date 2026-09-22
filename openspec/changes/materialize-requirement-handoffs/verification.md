# Verification: Idempotent Requirement handoff materialization

## Semantic review

Reviewed the proposal, design, delta, implementation, and tests together. The adapter accepts only a currently ready handoff listed by the Requirement orchestrator and an independently authored managed bundle. It computes a stable parent-plus-handoff identity, embeds it and the Requirement back-reference before managed-task publication, and delegates package validation/creation to the existing managed intake. On retry, it scans both open and closed Issues for that identity, rejects ambiguous or conflicting candidates, and verifies both link directions after repair. A failed link cannot be reported as success. OpenSpec remains the child authority after materialization; no second ledger is written.

## Checks actually run

- `python3 -m unittest tests.test_requirement_intake tests.test_managed_task tests.test_orchestrate_pre_authoring -q` — 129 tests passed.
- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `openspec validate materialize-requirement-handoffs --strict` — passed.
- `git diff --check` — passed.

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/delta/implementation plus focused and lifecycle automated regression checks
Automated-Checks-Evidence: automated-checks.json
