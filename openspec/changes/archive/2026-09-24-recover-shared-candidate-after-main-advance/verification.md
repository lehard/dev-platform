OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal, design, specification scenarios, implementation and Git-backed refusal/replay tests; openspec validate --strict; full repository test groups.
Automated-Checks-Evidence: automated-checks.json
Requirement-Integration-Exception: Publish the recovery primitive independently so the stale shared #164 candidate can be safely regenerated from current main before the remaining children are integrated.

Outcome: A moved main selects a distinct base-bound candidate generation and exact child delta bases; the older candidate and child branches remain unchanged. Exact branch-head, overlap, manifest, clean-worktree and protected publication gates remain in force.
Evidence: `python3 -m unittest tests.test_requirement_integration -v` (18 tests passed); `python3 -m compileall -q template/scripts scripts`; `python3 scripts/managed_projects.py validate`; `python3 scripts/run_test_groups.py --all` (13 groups passed, 1272 tests discovered); `python3 template/scripts/openspec_lifecycle.py check`; `openspec validate recover-shared-candidate-after-main-advance --strict` (valid).
Limit: The real #164 protected publication and terminal board reconciliation remain to be executed after this independent recovery task merges; this receipt claims only #192 implementation and checks.
