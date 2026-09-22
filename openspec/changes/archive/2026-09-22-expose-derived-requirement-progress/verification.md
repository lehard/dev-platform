# Verification: Derived Requirement progress

## Semantic review

Reviewed proposal, design, delta, implementation and tests together. `aggregate` keeps its child-only `status` field for compatibility and adds a recomputed `progress` projection with stage, reason, diagnostics and source evidence. Before child materialization it reads the local orchestrator to distinguish pre-authoring, design, human decision, readiness, blocked and unknown. Once children exist, their authoritative Project lifecycle governs implementation/completion; machine-local pre-authoring state is no longer required. Unreadable/contradictory required sources fail closed, explicit child blocking reports blocked, and all linked children must be Done for `progress.stage=done`. No Requirement status field or ledger is written.

## Checks actually run

- `python3 -m unittest tests.test_requirement_intake tests.test_orchestrate_pre_authoring -q` — 50 tests passed.
- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed.
- `openspec validate expose-derived-requirement-progress --strict` — passed.
- `git diff --check` — passed.

OpenSpec-Verify: PASS
Verification-Method: manual semantic review of proposal/design/delta/implementation plus focused and lifecycle automated regression checks
Automated-Checks-Evidence: automated-checks.json
