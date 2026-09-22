# Verification: Proportional Requirement pre-authoring

## Semantic review

Reviewed proposal, design, specification delta, code, and tests together. Depth is an explicit recorded judgment with reason and complete Requirement binding. Deterministic work needs no snapshot or ADD; bounded evidence requires an explicit concern subset and routine-read-only routing; material design retains the full snapshot, ADD, intents and R2-default path. Skip receipts and direct handoffs are derived from current bindings on every status call. A Requirement change invalidates selection and descendants while preserving independently freshenable project evidence. Escalation-required projections block handoff. No material mismatch was found.

## Checks actually run

- `python3 -m unittest tests.test_orchestrate_pre_authoring tests.test_requirement_intake tests.test_project_evidence -q` — 51 tests passed before the final two regression cases were added.
- `python3 scripts/run_test_groups.py --all` — 13 of 13 groups passed, 1,151 declared/discovered tests, before the final two regression cases were added. The archive lifecycle will rerun the authoritative checks.
- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- `openspec validate make-requirement-preauthoring-proportional --strict` — passed.

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/delta/implementation plus focused and full automated regression checks
Automated-Checks-Evidence: automated-checks.json
