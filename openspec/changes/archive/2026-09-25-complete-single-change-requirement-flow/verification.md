# Verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal, design, tasks and the agent-workflow delta against the implementation and exercised paths.
Automated-Checks-Evidence: automated-checks.json

The implementation consumes real deterministic, bounded-evidence and material multi-child handoffs from `orchestrate_pre_authoring.status`; tests exercise those envelopes through `execute_requirement.advance`. Direct handoff enters one managed child, which retains its writer claim through ordinary finish. Multi-child delivery retains the shared candidate and releases only verified ready writer claims. Exact merged delivery, archived provenance, reciprocal links, terminal child status and Issue closure gate the parent Done transition. Shared candidate cleanup records exact worktree, branch and head identity after terminal proof; ordinary child finish retains its existing targeted cleanup. Central and template guidance describe these same transitions.

Checks run: `python3 -m compileall -q template/scripts scripts`; `python3 scripts/managed_projects.py validate` (3 managed, 0 candidate, 0 excluded); `python3 scripts/run_test_groups.py --all` (1320 declared/discovered tests, 13 groups, all passed); `python3 template/scripts/openspec_lifecycle.py check`; `openspec validate complete-single-change-requirement-flow --strict`. The archive helper will produce `automated-checks.json` from its own selected checks.

Historical #154, #157 and #158 were inspected read-only: all linked children are closed, Project Done and archived on main. Their parent mutation is a post-publication terminal reconciliation step, so it is not claimed as pre-merge verification.

The first GitHub CI run for PR #126 exposed an introduced test-fixture portability error: the new end-to-end repository inherited the host's default Git branch, which is `master` on the CI runner. The test fixture now explicitly names its integration branch `main`, matching the executor precondition. This was a fixture error, not a production transition failure; the three affected end-to-end scenarios pass after the correction. Updated automated evidence and the next CI run cover the corrected candidate.
