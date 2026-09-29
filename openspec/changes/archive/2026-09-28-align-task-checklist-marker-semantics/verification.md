# Verification: align-task-checklist-marker-semantics

OpenSpec-Verify: PASS

Verification-Method: Manual semantic review of the source Requirement, proposal, design, tasks and completion-lifecycle delta against the implementation and the upstream OpenSpec 1.13.2 `dist/utils/task-progress.js` task-line pattern (read from the published npm package); defect reproduction against the pre-change helper; focused and parallel full-suite execution; strict OpenSpec validation.

Automated-Checks-Evidence: automated-checks.json

## Outcome and evidence

- Defect reproduced before the fix: the pre-change `task_state` returned `(1, 0)` (complete) for a tasks.md holding `- [x] done` plus any one of `+ [ ] task`, `* [ ] task`, `1. [ ] task`, `1) [ ] task` or `- [~] partial`.
- After the fix, `task_state` returns `(2, 1)` for each of those, `completed_active_changes` does not report the change, and `require_ready` refuses it with `1 of 2 task(s) remain incomplete`.
- `- [ ]`, `- [x]` and `- [X]` counting is unchanged; Markdown links such as `- [x](url)` and `- [x][ref]` are not counted, matching upstream.
- `managed_task._task_completion` and the archived-tasks check in `requirement_integration` now delegate to the same `openspec_lifecycle.count_tasks` rule instead of carrying their own `-`-only regex. Their existing tests pass in the full suite. No dedicated alternative-marker test was added at those two call sites; the shared rule is covered in `tests/test_openspec_lifecycle.py`.
- `scripts/openspec_lifecycle.py` is a `source_adapter` shim over the template helper, so the dogfood and template copies cannot diverge.

## Automated checks

- `python3 -m unittest tests.test_openspec_lifecycle`: passed, 25 tests.
- `DEV_PLATFORM_TEST_JOBS=3 python3 scripts/run_test_groups.py --all`: passed before reconciliation (14 groups at that revision).
- After reconciliation to `main` at `d61e65f`, `python3 scripts/run_test_groups.py --all --quiet` passed 14 of 15 groups. `fast-c` failed because the worktree's ignored `.ruff_cache` contained unreadable files, which `test_root_guidance_contract` attempted to copy. After moving that cache out of the worktree, `python3 scripts/run_test_groups.py --group fast-c --quiet` passed. The same reconciled code was used for both runs.
- `PYTHONPYCACHEPREFIX=/tmp/dev-platform-264-pycache python3 -m compileall -q template/scripts scripts`: passed after reconciliation. The default cache location had pre-existing files owned by another local account and was not writable.
- `python3 -m ruff check scripts template/scripts tests`: passed.
- `python3 scripts/managed_projects.py validate`: passed (3 managed projects).
- `python3 template/scripts/openspec_lifecycle.py check`: reports this completed active change pending archive, as expected.
- `openspec validate align-task-checklist-marker-semantics --strict`: passed.
- `git diff --check`: passed.

## Semantic OpenSpec review

- **Outcome:** No platform gate can treat a change as complete while an unfinished checklist item uses a non-`-` marker or non-`x` checkbox content.
- **Completeness:** The delta covers alternative markers, unknown content and unchanged standard checkboxes. The implementation covers every gate the delta names: lifecycle readiness/archive, hygiene, managed delivery provenance and shared Requirement integration.
- **Correctness:** The Python pattern is a direct port of upstream `TASK_LINE_PATTERN`; completion is `content.lower() == "x"`, so empty and any other recognized content are incomplete.
- **Coherence:** Requirement, proposal, design, delta, tasks and code describe one counting rule. Design and tasks were updated before implementation to add the two duplicated counters. The Requirement child-list parser is platform-written machine state and is explicitly out of scope.

The archive helper will generate `automated-checks.json` for the exact archive candidate; this marker names that expected evidence.
