# Semantic verification

OpenSpec-Verify: PASS
Verification-Method: Manual completeness/correctness/coherence review against the managed OpenSpec delta, targeted regression tests, full platform test suite, Copier render smoke, and live guarded Codex acceptance.

## Review result

- **Completeness:** `delegated_write_guard.py` now normalizes `integration_root`, `assigned_worktree`, `/tmp`, `$TMPDIR`, and Python's active temporary root before a Codex `HARD` decision. It records the concrete overlap in the downgrade detail, preserves the existing detection-only dirty-integration precondition, and refuses `--require-hard` before child launch.
- **Correctness:** Regression coverage proves a normal topology can be `HARD`; `/tmp`, assigned-worktree, custom `$TMPDIR`, and symlinked overlaps are not. The CLI smoke confirms an unsafe `--require-hard` invocation exits before its child marker can be created.
- **Coherence:** The modified `platform-delegation` requirement preserves all pre-existing containment scenarios while refining `HARD` to cover protected repository paths rather than the entire filesystem. Source and generated agent guidance use the same topology-aware definition.

## Executed evidence

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 -m unittest discover -s tests -v`
- `python3 scripts/select_checks.py --execute`
- `python3 template/scripts/openspec_lifecycle.py check`
- Copier multi-agent/platform render plus generated-script compilation.
- Live Codex CLI `0.146.1`, which advertised `workspace-write` and reported its writable surface as `[workdir, /tmp, $TMPDIR]`:
  - safe `/Users/Shared/Workspace/...` topology ran through the guard at `hard` tier and returned `SAFE_ACCEPTANCE`;
  - a real registered git worktree under the active system temp root was refused with `--require-hard`, exit `2`, before child execution.

`VERSION` is advanced to `1.4.25`, so the normal protected-main release workflow will create the immutable release and dispatch the standard rollout after merge.
