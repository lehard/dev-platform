# Verification: friction promotion

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the outcome, new scenario requirements, command implementation and regression assertions; focused and full platform tests.
Automated-Checks-Evidence: automated-checks.json

The command now reads the current project configuration before rendering the promotion candidate. The operator-owned destination and sanitized body remain unchanged. The regression calls the command parser for dry-run and the promotion function for the configured GitHub destination. The implementation matches the active delta and introduces no second task state.

Executed before archive:

- `python3 -m unittest tests.test_friction_review -q` — 46 passed.
- `python3 scripts/select_checks.py --base origin/main --execute` — compileall and all platform test groups passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- `openspec validate fix-friction-promotion --strict --no-interactive` — pending below.

The archive helper will produce `automated-checks.json` for its exact check run.
