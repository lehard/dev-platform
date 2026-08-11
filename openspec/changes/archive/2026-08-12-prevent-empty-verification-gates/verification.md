# Verification

Implemented-review confirms the accepted change is complete and coherent:

- `select_checks.py` now models `not-applicable`, `ready`, and `invalid-coverage` separately, blocks empty/malformed/missing-required platform evidence, and leaves `harness_mode=project` non-blocking.
- The lifecycle records the exact commands that it executes and refuses a platform-owned archive unless that generated evidence is cited and shows successful, non-empty coverage.
- Check metadata can require `test` evidence separately from syntax/compilation, without imposing a framework on project-owned harnesses.

Automated verification completed:

- `python3 -m unittest discover -s tests -q` — 391 tests passed.
- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `openspec validate --all --strict --no-interactive`
- `git diff --check`

Copier is not installed on this host, so its render smoke was not applicable. The archive helper will generate the cited command-level evidence below from the actual platform-owned selected checks.

OpenSpec-Verify: PASS
Verification-Method: equivalent-review
Automated-Checks-Evidence: automated-checks.json
