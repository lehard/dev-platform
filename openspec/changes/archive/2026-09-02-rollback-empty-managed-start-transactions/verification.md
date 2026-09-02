# Verification: Roll back empty managed-start transactions

OpenSpec-Verify: PASS
Verification-Method: manual equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration available in this environment) plus `openspec validate rollback-empty-managed-start-transactions --strict --no-interactive` and the full platform test suite via `scripts/run_test_groups.py --all`
Automated-Checks-Evidence: automated-checks.json

## Completeness

Capability delta `managed-task-intake` adds one requirement, "Empty managed-start transactions are recoverable without manual state editing", with three scenarios. Each is implemented in `template/scripts/start_managed_task.py` and covered by tests in `tests/managed_start_transaction_cases.py` (test group `managed_task_exact_state`, aggregator `tests/test_managed_task_exact_state.py`).

- Shared emptiness proof: `_managed_start_left_no_task_state(root, worktree, branch)` returns `True` only when the exact worktree path does not exist, the `refs/heads/agent/<change>` branch ref is absent, and `_board_item_for_identity` finds no exact board entry. Ambiguous board state (`>1` match) propagates the existing `ManagedTaskError` from `_board_item_for_identity` rather than reporting emptiness. The helper is called from both the transaction failure handler and the retry supersession guard.

- Scenario "Package validation fails before task state exists": in `managed_start_transaction` the `except Exception` arm now runs the emptiness proof before re-raising; if the attempt provably created no worktree, branch or board entry, the exact transaction file is removed with `path.unlink(missing_ok=True)`. The original in-flight exception is always re-raised. If the proof itself raises, the handler falls closed (`empty = False`) and keeps the transaction. `ManagedAdmissionWait` is re-raised by a dedicated narrower `except` placed before the broad handler, so a WAIT admission still retains its transaction/worktree/package.
  - Covered by `test_failed_validation_before_mutation_rolls_back_transaction` (nothing created -> receipt removed, no worktree, no branch) and, for the WAIT carve-out, `test_wait_admission_retains_transaction`.

- Scenario "Corrected package retries after an empty failure": when an existing transaction file is present (`created` is `False`), the only mismatching `expected` field is `package_revision`, the recorded `state` is `creating`, and `_managed_start_left_no_task_state` is `True`, the stale record is rebuilt in place from `_fresh_transaction()` (new `attempt_id`, `package_revision`, `created_at`) and start proceeds through the normal `_start_new_managed_task` path. `recover_incomplete_managed_start` already returns `False` early when worktree, branch and board are all absent, so it needed no change (confirmed by reading it).
  - Covered by `test_corrected_package_revision_supersedes_proven_empty_transaction` (stale `package_revision`, all side effects absent -> no "does not match" error, new `attempt_id`, corrected `package_revision` visible to the downstream start, receipt retired on success).

- Scenario "Partial state exists": every other mismatch, a non-`creating` state, or any proven/ambiguous leftover state still raises the unchanged `"existing managed-start transaction does not match the requested package"` `ManagedTaskError`; the pre-yield `atomic_write_text` is the last write, so `locked_json` leaves the stale receipt byte-for-byte intact on that raise.
  - Covered by `test_supersession_fails_closed_when_branch_exists`, `test_supersession_fails_closed_when_worktree_exists`, `test_supersession_fails_closed_when_board_entry_exists` (each asserts the "does not match" `ManagedTaskError` and an unchanged receipt), `test_ambiguous_board_never_supersedes_transaction` (board lookup raising -> transaction neither deleted nor replaced), and `test_interrupted_start_after_partial_mutation_keeps_retry_receipt` (a failure *after* the fake `start_task` creates the worktree keeps the `creating` receipt).
  - The pre-existing conservative recovery diagnostics are untouched: `test_recovery_preserves_unrelated_dirty_worktree`, `test_board_lookup_is_fenced_to_exact_task_identity`, and `test_unregistered_path_is_never_deleted_as_retry_debris` still pass unchanged.

## Correctness

- `mismatches == ["package_revision"]` is an exact-list comparison; because `expected` is built in a fixed insertion order and compared in that order, any additional differing field (or a differing `package_revision` alongside anything else) yields a longer list and falls through to the unchanged raise. Same-revision resume (empty `mismatches`) is unaffected — the supersession branch is skipped and the final redundant `mismatches` re-check still runs.
- Fail-closed ordering: the supersession guard evaluates `_managed_start_left_no_task_state` only after the cheap `mismatches`/`state` predicates, and any exception from the board lookup propagates out of `managed_start_transaction` before `yield`, so no partial write occurs.
- The exception-cleanup proof is wrapped in its own `try/except` that swallows only the proof's failure (setting `empty = False`); the original exception object is preserved and re-raised by the bare `raise`.
- `.resolve()` continues to be applied to the transaction `worktree` before every identity comparison, matching the realpath convention used by `_registered_worktrees`, `_board_item_for_identity` and `git worktree list --porcelain`. New tests build their expected `worktree`/`task_root` with `.resolve()` for the same reason.
- Non-multi-agent start (`profile != "multi-agent"`) and the genuine-resume path (`_resume_existing_managed_task`) are unchanged.

## Coherence

- All behavioral changes are in `template/scripts/start_managed_task.py`, which ships to downstream Copier-managed projects; `scripts/start_managed_task.py` remains a pure `runpy` shim (unchanged).
- No new CLI flags, commands or user-facing surfaces; the `docs/engineering/*` entrypoint descriptions remain accurate. `scripts/check_docs_links.py` reports no problems.
- The existing `managed_task_exact_state` test group already discovers the new cases through the `tests/test_managed_task_exact_state.py` aggregator; `scripts/run_test_groups.py --all` reports exact discovery/declared equivalence (`declared_test_count == discovered_test_count == 830`, `missing_from_groups: []`, `declared_but_not_discovered: []`), so both counts moved together with the 8 added tests. No pinned count or manifest exists to hand-edit.
- No change to release refs, rollout registry, or provider-local routing surfaces.

## Acceptance evidence (commands actually run from the task worktree)

- `python3 -m compileall -q template/scripts scripts` — pass (exit 0).
- `python3 scripts/run_test_groups.py --group managed_task_exact_state` — pass; `outcome: "success"`, all 21 tests in the group (13 in `managed_start_transaction_cases`, 8 in `managed_task_exact_state_cases`).
- `python3 -m unittest -v managed_start_transaction_cases` (from `tests/`) — `Ran 13 tests ... OK`.
- `python3 scripts/run_test_groups.py --all` — pass; `DEV_PLATFORM_TEST_AGGREGATE ... "failed_groups": [], "group_count": 13, "outcome": "success"`; `DEV_PLATFORM_TEST_COVERAGE ... "declared_test_count": 830, "discovered_test_count": 830, "missing_from_groups": [], "declared_but_not_discovered": [], "duplicated_tests": []`.
- `python3 template/scripts/openspec_lifecycle.py check` — `OpenSpec lifecycle hygiene: OK`.
- `python3 scripts/managed_projects.py validate` — `Managed project registry: OK (3 managed, 7 candidate, 3 excluded)`.
- `openspec validate rollback-empty-managed-start-transactions --strict --no-interactive` — `Change 'rollback-empty-managed-start-transactions' is valid`.
- `python3 scripts/check_docs_links.py` — `Documentation link/anchor check: no problems found.`
- `python3 scripts/select_checks.py --base origin/main --execute --evidence openspec/changes/rollback-empty-managed-start-transactions/automated-checks.json` — `outcome: "success"`, 3/3 selected commands succeeded (see `automated-checks.json`).

No CRITICAL or WARNING findings remain. The change is verified; archive and publication are left to the managed lifecycle owner (not performed here).
