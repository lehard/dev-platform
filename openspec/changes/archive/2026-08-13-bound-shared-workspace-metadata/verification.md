# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the active delta against the implemented allowlist, ownership boundaries and regression coverage.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- The audit set is now derived from registered lifecycle paths plus the integration root and required Git common-directory metadata; it no longer enumerates arbitrary `.claude` children.
- Registered lifecycle paths retain symlink and boundary checks, recursive traversal is limited to owned friction and routing state, and worktree contents remain excluded.
- Regression fixtures demonstrate that an external foreign symlink and `node_modules.partial.*` cache are untouched, while restrictive owned Git and lifecycle state remain repaired.
- The implementation, delta requirements, design and user-facing guidance agree; no material conflict with current specifications or active changes was found.

## Automated checks

- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/bound-shared-workspace-metadata/automated-checks.json`
  - `python3 -m compileall -q template/scripts scripts`
  - `python3 scripts/managed_projects.py validate`
  - `python3 scripts/run_test_groups.py --all`
- `TMPDIR=/Users/Shared/Workspace PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_shared_workspace` (9 tests)
- `TMPDIR=/Users/Shared/Workspace PYTHONDONTWRITEBYTECODE=1 python3 tests/project_harness_adoption_smoke.py`
- `openspec validate bound-shared-workspace-metadata --strict --no-interactive`
- `git diff --check`

The temporary directory for the shared-workspace and Copier smoke was placed under `/Users/Shared/Workspace`, whose group-capable filesystem preserves the required setgid bit. The macOS system temporary filesystem does not preserve that bit and is unsuitable for this permission-contract smoke.
