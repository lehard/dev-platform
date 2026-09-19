# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic review because installed OpenSpec CLI 1.8.0 has no `verify` command; reviewed the proposal, design, delta spec, implementation, and tests for outcome fidelity, completeness, correctness, and coherence.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- **Outcome fidelity:** the public-distribution candidate set is now derived from `git ls-files -z` in `scripts/public_distribution.py` (`tracked_files`/`public_files`) instead of `root.rglob("*")`, with the existing `EXCLUDED_PARTS`/`EXCLUDED_PATHS`/cutover-policy exclusion logic applied unchanged on top. The command fails closed with `GitSourceError` (a `ValueError` subclass, so existing CLI error handling for `snapshot` catches it unchanged; `audit`'s handler was extended to also catch it) when `root` is not a readable Git checkout, with no filesystem-walk fallback.
- **Completeness:** covers the three requested behaviors — untracked files never enter the candidate set/digest/findings/snapshot; tracked files with the same material still block audit exactly as before; running outside a Git checkout fails closed.
- **Correctness:** new regression tests construct real Git checkouts (`git init`/`git add`, no mock) and assert: an untracked file with a cutover-policy marker is absent from `candidate_files`, does not move `candidate_sha256`, produces no finding, and is absent from the snapshot tar; the same marker committed as a tracked file still produces `operator_state`/`compatibility_markers` findings and blocks `snapshot()`; `public_files`/`audit_tree`/`snapshot` all raise `GitSourceError` against a non-Git directory. All 15 pre-existing `public_distribution` tests were updated to `git init`/`git add` their fixtures (no assertion changes) and remain green. `tests/public_distribution_snapshot_smoke.py` was reordered (fresh-history establishment now precedes the extracted-tree completeness re-check, since that re-check also calls `public_files()`) and passes end-to-end, including the full `run_test_groups.py --all` re-run from inside the extracted, freshly-git-initialized snapshot.
- **Coherence:** no change to `EXCLUDED_PARTS`, `EXCLUDED_PATHS`, `PROHIBITED_PATHS`, `SECRET_PATTERNS`, the cutover-policy schema, or the canonical-repository allowlist. `audit` and `snapshot` still consume the exact same `public_files()` call site. The accepted `public-distribution` requirement "Public audit covers the exact public snapshot candidate set" was updated (MODIFIED) to state the Git-tracked source and the new untracked/fail-closed guarantees explicitly, with two new scenarios plus the fail-closed scenario.

## Executed evidence

- `python3 -m compileall -q template/scripts scripts`
- `python3 -m pytest tests/test_public_distribution.py -q` — 20 tests, all passing (6 new/renamed regression cases + 14 pre-existing, updated fixtures).
- `python3 tests/public_distribution_snapshot_smoke.py` — snapshot built (351 files), extracted, fresh history established, completeness re-check passed, full `run_test_groups.py --all` (13 groups, all successful) and `openspec_lifecycle.py check` re-run from inside the extracted tree.
- `python3 scripts/run_test_groups.py --all` — full grouped suite, all successful, from the task worktree.
- `python3 scripts/managed_projects.py --registry tests/fixtures/managed-projects.json validate` — OK (the live local `--registry`-less path is separately blocked by this operator's own `rollout.registry_path`-less `operator.toml`, confirmed pre-existing and identical on `main`; unrelated to this change).
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate scope-public-distribution-candidates-to-git-tracked-source --strict --no-interactive`
