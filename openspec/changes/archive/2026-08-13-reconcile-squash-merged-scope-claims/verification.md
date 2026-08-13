# Verification: Reconcile squash-merged scope claims

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of the proposal, design, delta specifications and implementation; automated targeted regression coverage plus the protected full platform validation suite.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Exact task publication lookup binds the registered branch, configured base and local branch head, then accepts only GitHub `MERGED` state.
- Scope gating treats only that proven terminal state as complete; open, stale-head, malformed, unavailable and unauthenticated responses retain the claim.
- Reconciliation is limited to board-status/coordination metadata. Tests prove a dirty sibling worktree remains present and unchanged, and repeated clean-board reconciliation converges.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 scripts/run_test_groups.py --all`
- `python3 template/scripts/openspec_lifecycle.py check`
- `git diff --check`

The targeted worktree, publication-state and lifecycle regressions cover the new squash-merge path and its active/unavailable controls.
