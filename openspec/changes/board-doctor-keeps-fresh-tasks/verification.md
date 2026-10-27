OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review of the agent_board.py and test diff against the worktree-coordination delta, proposal, design and tasks; targeted unittest run of tests/test_worktree_hygiene.py on Python 3.11 (64 tests OK); repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope

`agent_board.py doctor --fix` no longer removes a freshly registered task without commits. Only `template/scripts/agent_board.py`, its manifest entry and `tests/test_worktree_hygiene.py` change.

## Completeness

- Registration base: `cmd_start` records `base_head` from the registered branch head; an unresolvable branch stops with an explicit error (`_branch_head`), no default. Test: `test_registration_records_the_branch_head_as_its_base`.
- Fresh task survives (scenario 1): `_ancestor_merge_problem` returns no problem when the branch still points at `base_head`, even after `main` advances. Test: `test_fresh_registered_task_without_commits_survives_doctor_fix` registers through `cmd_start`, commits on main, runs `cmd_doctor --fix` and keeps the entry and worktree.
- Merged and abandoned task removed (scenario 2): a branch that moved on from its base and whose tip is not on main's first-parent line since that base (it entered main as a merge parent) gives `merged-branch`; `doctor --fix` removes the clean entry. Tests: `test_merged_and_abandoned_task_is_removed_by_doctor_fix`, `test_status_detects_merged_branch_and_stale_heartbeat`; the exact-PR path for a fast-forward merge stays terminal (`test_exact_merged_pr_proves_a_fast_forwarded_branch`).
- Unprovable merge kept with a named reason (scenario 3): no base, an unknown base, or a moved tip that lies on main's first-parent line (or no longer descends from its base) without an exact merged PR yield `unproven-merge-no-base`, `unproven-merge-base-unknown`, `unproven-merge-no-own-commits`; they are not terminal, so the entry is `degraded`, `_safe_to_remove` is false, and JSON/text output carry the reason. Test: `test_unproven_merges_are_kept_with_named_reasons`.
- Review repair (spec-fidelity finding `ff-over-merge-commits-misclassified-merged`): the earlier per-commit check counted second-parent commits of a `--no-ff` merge that a commitless task fast-forwarded over as own merged commits. The branch tip now decides. Test: `test_commitless_task_fast_forwarded_over_a_merge_commit_survives_doctor_fix` (fresh task, `--no-ff` merge on main, fast-forward of the branch, `doctor --fix` keeps it as `unproven-merge-no-own-commits`). Advisory finding `ff-merged-entries-accumulate-without-pr-proof` is the accepted design trade-off: such entries leave the board through the task's normal finish.
- Git failures other than "not a commit" (`rev-parse --verify --quiet` exit 1) still raise, as `_merged_into` does; no fallback was added.
- The existing dirty-terminal-sibling test now registers `base_head` and merges with `--no-ff`, which also stops it from reaching the real GitHub lookup.

All tasks in `tasks.md` are complete.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence ...` on repaired head dfa5b0fa passed: compileall, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all` (affected precheck also green).
