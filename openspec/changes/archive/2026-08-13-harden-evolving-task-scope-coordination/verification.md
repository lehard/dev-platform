# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic OpenSpec review against proposal, design and delta specs (no `/opsx:verify` tool integration available in this environment); focused and full local automated validation; live dogfood of the new gate against the real multi-agent agent board
Automated-Checks-Evidence: automated-checks.json

## Completeness

- `agent_board.py` gained a bounded `acknowledge` subcommand that records evidence (current/conflicting task identity, exact conflicting repository-relative paths, a required reason) only for paths it proves are currently, genuinely conflicting; `_admission_conflicts` (shared by admission and the new rescope gate) now skips a conflict only when a matching acknowledgment exists, so declared/factual scope is never falsified to get past admission.
- `hard_scope_conflicts`/`enforce_scope_gate` reuse the existing concrete-claim comparison read-only to recheck evolving factual scope. They are wired at two checkpoints: `select_checks.py` immediately before it runs commands selected for `protected-full`/`high-impact-path`/`unknown-path` reasons (before costly validation), and `finish_task.py` immediately before publication (right after `run_checks` succeeds, before the PR/direct publish path). Both raise `HardScopeOverlap` on a new unacknowledged hard overlap and leave soft/directory overlap as the pre-existing advisory-only warning.
- `managed_project_status.py` gained `block_for_scope_conflict`/`resume_from_scope_conflict`, best-effort helpers (no-op for a quick/non-managed task or when GitHub Project access is unavailable) that reconcile a genuine scope-coordination stop to `Blocked` and, on the next successful recheck, return it to the truthful nonterminal state derived from current PR evidence. The pre-existing admission-time `WAIT` -> `Blocked`/`In progress` reconciliation in `start_managed_task.py` was already correct and needed no change; it is exercised by the same acknowledgment-aware `_admission_conflicts`.
- `start_task.py`'s `admission_reason` now tells the operator how to resolve a `WAIT` (`agent_board.py acknowledge ...`) instead of only naming the conflict.

## Correctness

- Focused unit coverage (`tests/test_worktree_hygiene.py::AgentBoardAcknowledgmentTests`) verifies: an acknowledged overlap allows `RUN` while the path stays in `claims` (no scope narrowing); acknowledgment rejects a path that is not currently conflicting, an empty reason, an empty path list, an unknown board id, and a stale/inactive conflicting task; an acknowledgment for one path never authorizes a later, different overlapping path (new hard overlap requires a new decision); the rescope gate ignores a completed/merged sibling's stale claim; the rescope gate is silent when no active overlap exists.
- Integration coverage (`tests/test_git_lifecycle.py`) reproduces the exact regressions this change targets: `test_protected_full_validation_blocks_before_costly_commands_run` proves `select_checks.py --mode protected-full --execute` stops before any selected command runs (dev-platform#220 -- previously only a `finish`-time warning); `test_multi_agent_direct_finish_blocks_then_resolves_new_hard_overlap` proves `finish_task.py` blocks publication on a hard overlap introduced after admission and that acknowledging it (dev-platform#203) resolves the block so the task publishes; `test_finish_task_tolerates_legacy_agent_board_without_overlap_helper` continues to pass unmodified, so the Copier-upgrade compatibility shim still works with the new symbols added to it.
- `tests/test_managed_project_status.py` verifies `block_for_scope_conflict` sets `Blocked` and is a no-op for a quick task without managed provenance, and `resume_from_scope_conflict` is a no-op unless currently `Blocked` and otherwise reconciles to the derived nonterminal status.
- Existing race-safety coverage (`test_concurrent_exact_claims_cannot_both_run`) is untouched and still passes: acknowledgment only filters which conflicts are reported/raised, never the atomic locked read-and-claim critical section.
- A real regression was found and fixed during this task: `select_checks.py`'s new gate call went through `board_path()` unconditionally, which raises `KeyError` for a platform config that declares no `[paths] agent_board` at all (e.g. `standard`/`light` profile fixtures) instead of treating "board not configured for this profile" as "no board to recheck". Fixed by catching `KeyError` in `hard_scope_conflicts` and treating it the same as a missing board file. `python3 -m unittest discover -s tests` caught this via `tests/test_task_freshness.py` before it could reach main.
- Live dogfood: running this task's own new gate against the real `.claude/agents-board.json` on this machine found a genuine three-way hard overlap on `template/scripts/finish_task.py` with two other currently active managed tasks (`lehard/development-backlog#34`, `#38`). `git diff` against each sibling branch confirmed their edits land in distinct, non-overlapping regions of the file (different imports/fallbacks, different functions). Both overlaps were resolved with `agent_board.py acknowledge` and bounded reasons, after which `hard_scope_conflicts` returned empty -- proving the acknowledgment path end-to-end against real, unmodified sibling task state, not only synthetic fixtures.

## Automated validation

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 scripts/run_test_groups.py --all` (566 tests across all groups, 0 failures)
- `openspec validate harden-evolving-task-scope-coordination --strict`
- `python3 template/scripts/openspec_lifecycle.py check`

## Coherence

The implementation extends the single existing coordination store (`_admission_conflicts`, `_claim_candidates`, `_status`) rather than introducing a second scope engine, a scheduler, sub-file/line locking, or automatic conflict resolution -- matching design.md's explicit non-goals. Hard overlap stays exact-concrete-file; soft/directory overlap stays advisory-only by construction, because the rescope gate reuses the same concrete-only claim comparison as admission. No unresolved material findings remain.
