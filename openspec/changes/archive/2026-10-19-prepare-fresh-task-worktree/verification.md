OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the supervisor-written diff against the engineering-capabilities and shared-workspace-safety deltas, proposal, design and tasks; defect reproduced by the new tests on the pre-change scripts before the fix; repository-owned selected checks on the committed head.
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

Independent review (claude/sonnet, spec-fidelity and engineering-quality) returned two advisory findings, both kept without code change:
- `git rev-parse --path-format=absolute` needs Git 2.31+: not a new requirement, `select_checks.py` and `local_workspace.py` already depend on the same flag on every lifecycle path.
- The "Shared-workspace audit after start" scenario has no test that runs the audit after creation: accepted as stated under "Not verified"; it is covered indirectly (no platform writer creates the private `info` directory, and the existing post-add `preflight(root)` repairs `.git/worktrees/**`).

Process note: the supervisor wrote the implementation before opening a delegation under a delegated-child routing plan; the routing gate blocked the checks and the owner explicitly approved the supervisor diff in chat (`model_routing.py approve-supervisor-diff`). A hard scope overlap with the sibling task #688 on the generated `template/dev-platform/platform-manifest.json` only was acknowledged on the board; source files are disjoint.

Completeness: every delta scenario has code and a test in `tests/test_fresh_worktree_readiness.py`.
- Fresh task worktree with selected capabilities: `start_worktree.create_worktree` runs `scripts/capability_manager.py sync` in the new worktree; the test uses the real `capability_manager.py`/`capability_evals.py` and a real descriptor (`systematic-bug-diagnosis`) with providers claude and codex, asserts both derived `SKILL.md` files exist, the real `--json audit` returns `ok`, and the worktree has no tracked change.
- Sync cannot complete: a failing manager makes start raise with the worktree path, the manager output and the sync command; worktree directory and branch are gone. Sync runs before board registration, so no board item exists.
- Doctor reports a stale surface: the failure line names `python3 scripts/capability_manager.py sync` and the doctor creates or changes no file.
- Readiness inside a linked worktree: `dev.ensure_local_generated_excludes` writes the common `info/exclude` (Git applies it in the linked worktree: `check-ignore AGENTS.local.md`) and creates no `info` directory under the private git dir.
- Shared-workspace audit after start: with no per-worktree `info` created by the platform, the existing post-add `preflight(root)` (repairing `.git/worktrees/**`) remains the last step before registration.

Correctness: on the pre-change scripts all four new tests failed (no surfaces, no error raised, private `info` created, no command in the hint); with the fix they pass. The existing rollback in `create_worktree` covers the new failure. No fallback or skip path was added; the doctor stays diagnostic-only.

Coherence: proposal, design, both delta specs and tasks agree. `template/dev-platform/platform-manifest.json` was regenerated. The new test module was registered in the `fast-a` group of `dev-platform/checks.toml`.

Additional repair (task 4.4): `tests/test_autonomous_integration_contour.py` used fixed 2026-10-01..03 dates for friction-window fixtures; they left the 14-day `AMBIGUOUS_WINDOW_DAYS` on 2026-10-17 and failed group `fast-b` on main independently of this change. Fixtures are now relative to the run time; the module's 56 tests pass.

Not verified: a direct test that runs the shared-workspace audit on a freshly created worktree (the test fixture stubs `preflight`); a live start through `start_managed_task` in a downstream project with enabled capabilities and a second OS account; the dev-platform repository itself enables no capability, so its own fresh worktrees exercise only the empty selection.

Checks actually run: `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/prepare-fresh-task-worktree/automated-checks.json` on head 69d92c21 (final task content): compileall success, ruff success, `run_test_groups.py --all` success (1321 s).

Post-finalize repair (coordinator, task 4.5): after merging main into the candidate, Platform CI failed three times in 'Smoke-test Copier upgrade paths' after the smoke printed 'passed': `TemporaryDirectory` cleanup raised `OSError: [Errno 39] Directory not empty` ('objects', then '.git'). Local Git 2.39 does not reproduce it; the runner has Git 2.55, whose commit spawns detached auto-maintenance. The smoke now sets `maintenance.auto=false` and `gc.auto=0` through `GIT_CONFIG_*`; the standard smoke passes locally. Not verified locally against Git 2.55; the CI run on the pushed head is the check.
