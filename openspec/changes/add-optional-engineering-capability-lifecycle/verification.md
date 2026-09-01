# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent manual semantic review of the accepted capability contract, descriptor/materialization implementation, provider support matrix, safety boundaries, and automated evidence.
Automated-Checks-Evidence: automated-checks.json

The review confirmed that canonical descriptors, project-owned opt-in, derived provider surfaces, parity/audit checks, catalog operations, and the bounded tool-backed path implement every accepted requirement without changing `workflow_profile` or claiming OpenSpec-generated skills. Invocation modes without documented native provider controls are explicitly reported as unsupported; they are not emulated.

Completed before archive:

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `openspec validate add-optional-engineering-capability-lifecycle --strict`
- `python3 scripts/run_test_groups.py --all` — passed: 13 groups, 750 declared/discovered tests.

An earlier full-suite attempt exposed a start-up race in an unrelated delegated-write test. The same test passed against `origin/main`, passed independently in this branch, and the final full suite passed; the initial failure is classified as an environmental nondeterminism rather than a change regression.
