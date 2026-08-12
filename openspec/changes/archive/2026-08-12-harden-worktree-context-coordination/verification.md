# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic OpenSpec review of completeness, correctness, and coherence, plus automated platform checks.

Reviewed behavior:

- Registration rejects relative, nested, missing, integration-main, and branch-mismatched worktree identities before it accesses or writes the board.
- Declared and factual repository-relative paths are compared only against valid active board entries. Diagnostics contain only task identity and bounded repository-relative paths, and remain advisory.
- Registration forwards diagnostics to the operator, while the same observation is repeated before the lifecycle's validation/publish path. Neither path performs automatic Git reconciliation or cleanup.

Automated checks:

- Automated-Checks-Evidence: automated-checks.json
- `python3 -m unittest discover -s tests -q`
- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate --all --strict --no-interactive`
