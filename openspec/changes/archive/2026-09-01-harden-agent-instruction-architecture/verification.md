# Verification: Harden agent-facing instruction architecture

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active proposal, design, delta spec, central/rendered instruction surfaces, and focused behavioral fixtures; automated structural and regression checks.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The delivered root-map pointers and thin Claude adapters preserve the stated
  bounded-map and single-owner architecture.
- The central and rendered task-intake/ChatGPT guidance retain one intent and
  package representation while documenting only their supported transport
  difference; normal repository intake remains unchanged.
- The focused fixtures exercise both authoring representations through the
  normal managed-package parser and preserve Backlog-only STOP semantics.
- No external instruction skill or ChatGPT service is required by the ordinary
  lifecycle sources.

## Checks run before receipt

- `python3 -m unittest tests/test_agent_instruction_architecture.py` — PASS
  (7 tests).
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS.
- `python3 scripts/run_test_groups.py --all` — PASS (741 discovered tests).
- `python3 template/scripts/openspec_lifecycle.py check` — PASS.
- `openspec validate harden-agent-instruction-architecture --strict --no-interactive` — PASS.

The lifecycle archive helper will generate `automated-checks.json` through the
selected-checks runner and validates that evidence before archiving.
