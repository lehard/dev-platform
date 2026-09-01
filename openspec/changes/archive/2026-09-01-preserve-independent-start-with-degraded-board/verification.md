# Verification: Preserve independent start with a degraded agent board

OpenSpec-Verify: PASS
Verification-Method: manual semantic review against proposal, design and delta specification plus focused regression and full platform test suite
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- Reviewed the implementation against every delta requirement: only a valid active worktree/branch identity contributes a blocking concrete-file claim; degraded and terminal sibling records remain bounded diagnostics; unreadable or un-lockable coordination state remains fail-closed.
- Confirmed that admission still executes under the existing locked JSON store and retains exact-file `WAIT`; the change neither repairs nor otherwise mutates sibling worktrees, branches or board records.
- Confirmed central and rendered guidance make the three outcomes distinct: non-blocking hygiene warning, `WAIT` for a valid concrete conflict, and blocked error for unsafe board access.
- Confirmed fresh-render and Copier-update smoke assertions preserve the new guidance. The environment does not have the `copier` executable, so the live Copier-render smoke is skipped rather than claimed as executed.

## Executed evidence

- Focused coordination/doctor/managed-start regressions — PASS, including mismatched and terminal dirty siblings remaining untouched, valid same-file `WAIT`, unreadable/lock failure, and outcome labeling.
- `python3 -m compileall -q template/scripts scripts` — PASS.
- `openspec validate preserve-independent-start-with-degraded-board --strict` — PASS.
- `python3 scripts/managed_projects.py validate` — PASS.
- `python3 template/scripts/openspec_lifecycle.py check` — PASS before archive.
- `python3 scripts/run_test_groups.py --all` — PASS: 748 declared/discovered tests across 13 groups; no failed groups.
- `git diff --check` — PASS.

## Coherence

The change extends the existing agent board and doctor surfaces rather than creating a second scheduler or coordination store. It keeps release rollout as an explicit later immutable-release operation: the present platform PR establishes tested rollout readiness and does not mutate a downstream default branch. No unresolved material findings remain.

## CI follow-up

PR #346 initially exposed an incorrect Copier smoke assertion: root `AGENTS.md` is project-owned and intentionally preserves local additions during update. The follow-up keeps the fresh-render assertion for root multi-agent guidance and checks the platform-owned rendered workflow in the Copier-update smoke. This corrects test ownership without changing the admitted-board behavior or the accepted specification.
