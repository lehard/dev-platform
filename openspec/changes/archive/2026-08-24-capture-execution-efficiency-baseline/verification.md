# Verification: Capture execution efficiency baseline

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review plus platform regression checks
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Compared the implementation to every added `model-routing` requirement: one existing routing-record path is extended with platform timing, supported structured usage, explicit unknowns, historical compatibility, and a bounded report.
- Confirmed the report derives completion/escalation data from routing provenance and verification context from the existing OpenSpec receipt; it introduces no separate execution or verification state machine.
- Confirmed `fresh_input_tokens` and `total_tokens` are not inferred when the runtime does not supply an unambiguous value, and missing measurements are never treated as zero.
- Confirmed completed execution records are mirrored into existing integration lifecycle state, so normal task-worktree cleanup does not erase baseline observations.

## Executed evidence

- `python3 -m unittest tests.test_model_routing` — PASS (41 tests).
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS.
- `python3 scripts/run_test_groups.py --all` — PASS (full declared coverage, 700 tests).
- `python3 scripts/model_routing.py efficiency-baseline` — real local sample reports a platform-measured elapsed duration and runtime-confirmed input/cache-read/output/request metrics; unavailable fresh-input/total metrics remain `unknown`, and the one-observation report is explicitly `insufficient`.
