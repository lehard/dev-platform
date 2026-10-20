OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the implementation diff against the friction-root-convergence-and-close-on-fix delta, proposal, design and tasks; repository-owned selected checks on the candidate head
Automated-Checks-Evidence: automated-checks.json

Implementation: a delegated native Claude executor implemented tasks 1.1-3.1 in `template/scripts/agent_friction.py`, the new workflow, documentation and tests. The supervisor reviewed the full diff and returned one repair to the same executor: `resolve-candidate --same-root` now appends the marker before commenting and guards the occurrence comment with a per-event marker, so a rerun after a partial failure posts one comment. The same repair added the `Fixes-Friction:` line for the candidate dead-end record to the proposal.

Completeness, each requirement scenario with its test in `tests/test_friction_root_convergence.py` (23 tests, in-memory GitHub fake behind the `gh` seam):
- A known root recurs under a new category. `resolve-candidate --same-root` adds an occurrence and the event's fingerprint marker to the target. A later event of that category is routed directly to the target, through the existing exact-marker scan in `route_event`; no routing change was needed.
- `--new-root` creates the issue through the shared `create_root_issue` helper, which `route_event` now also uses.
- Refusals: non-candidate event, closed target, non-generated target, repository mismatch.
- Open duplicates consolidated. `merge-roots`:
  - moves the markers to the target;
  - lists the duplicates on the target once;
  - closes each duplicate as `not_planned` with a pointer to the target.
  A rerun is a no-op. A closed duplicate that was not merged into the target is an error.
- Merged fix closes referenced records. `close-fixed`:
  - reads `Fixes-Friction:` lines from the PR body and from changed `openspec/changes/**/proposal.md` files at the merge commit;
  - validates every reference before closing anything;
  - closes with a comment naming the PR and merge commit;
  - leaves already-closed issues untouched;
  - does not comment twice on a rerun.
- No reference: nothing is closed.
- Named errors with nothing closed: a non-friction reference, a cross-repository reference, a malformed reference, or an unmerged PR.
- `close-fixed` does not read the operator configuration. A test makes that read fail and the command still runs.

Correctness: no fallback was introduced. GitHub failures in the new commands become a `SystemExit` that names the command and the failing request. A null PR body is treated as having no references: the data is absent, so nothing is masked. The workflow:
- runs only for merged PRs;
- has `contents: read`, `issues: write` and `pull-requests: read`;
- pins `actions/checkout` as `ci.yml` does;
- passes the PR number and repository through `env:`;
- carries a 10-minute timeout.

Coherence: the design decisions are implemented as written. Task 3.3 (consolidating the review sample) was moved out of this change: it operates on live issues after merge and is the Requirement's acceptance step. The workflow is platform-only and is not shipped to projects.

Known limits:
- The workflow relies on the runner's system `python3` and has not run in CI yet. It is exercised for the first time by this PR's own merge, which references one friction record.
- A wrong `--same-root` decision is visible in the occurrence comment but has no automatic undo.

Checks actually run:
- `python3 scripts/check_private_backlog_refs.py` passed.
- First `select_checks` run: stopped before validation on an unacknowledged scope overlap with a sibling task. The sibling changes the queue recovery line of `agent-workflow.md`; this task adds the friction paragraph there; the manifest is generated. The overlap was verified as disjoint and acknowledged with `agent_board.py acknowledge`.
- Second run: `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/friction-root-convergence-and-close-on-fix/automated-checks.json` on HEAD containing `origin/main` 3190580e, with the freshness gate passed. Its results:
  - `compileall` passed.
  - `ruff` passed.
  - `run_test_groups.py --all` passed in 1070 s.
