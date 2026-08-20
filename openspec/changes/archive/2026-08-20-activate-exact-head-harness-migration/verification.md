# Verification: activate exact-head harness migration

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active proposal, design,
delta specification, implementation, and executable regression evidence.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

The implementation inserts the reviewed Jara or Planner override before one
top-level `__main__` guard, so direct CLI execution binds exact-head functions
before the legacy `main()` runs. It reconstructs the legacy source only from
the reviewed SHA-256 predicate, including the known v1.4.34 append form, and
rejects ambiguous guards, partial surfaces, and unknown drift before a write.
The bounded functions preserve Jara's board/worktree/serialized path and
Planner's standalone integration-clone path; `harness_mode=platform` still
returns without migration.

## Executed evidence

- `python3 -m unittest tests.test_rollout_recopy -v` — PASS (37 tests),
  including direct `python script.py` executions for Jara-like and Planner-like
  migrated harnesses with stale merged head A versus current reused head B.
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS.
- `python3 template/scripts/openspec_lifecycle.py check` — PASS.
- `python3 scripts/run_test_groups.py --all` — PASS (672 tests / 13 groups,
  exit 0; group aggregate 606.739 seconds).
