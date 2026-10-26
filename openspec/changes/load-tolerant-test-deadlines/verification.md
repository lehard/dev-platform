OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review of the test diff against the platform-ci delta, proposal, design and tasks; ten repeated runs of the affected tests under artificial CPU oversubscription; repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope

Test-only slice of Requirement BR-812 (root friction lehard/dev-platform#124). Parallelism, the machine pool and product timeouts are unchanged. The 0.3 s case named in #124 (`test_publication_recovery_cli.py::test_expired_helper_fails_with_process_identity_and_retained_output`) already waits for a readiness marker written after the flushed partial output before its deadline starts, so it was left unchanged.

## Completeness

Each speed assertion was removed or replaced by an event-based proof or the shared bounded deadline (`tests/_concurrent_lifecycle.py`, 30 s):

- `test_git_lifecycle.py::test_run_checks_streams_child_output_incrementally`: removed the 1.0 s "first line promptly" bound; the load-monotonic "first line >1.5 s before return" proof stays.
- `test_delegated_write_guard.py::test_second_writer_is_refused_while_first_writer_owns_worktree`: 1 s start poll and 5 s join use the bounded deadline (the poll also stops when the launcher thread ended).
- `test_delegated_write_guard.py::_interrupt_self_when_ready`: 5 s readiness poll uses the bounded deadline.
- `test_pr_reconciliation_concurrency.py::test_already_merged_reconciliation_waits_for_existing_integration_lock`: the `>= 0.2 s` elapsed bound is replaced by the holder's release marker observed inside the serialized sync step; the lock timeout passed to the product is the bounded deadline instead of 2 s.
- `test_independent_review.py::test_timeout_kills_the_whole_reviewer_process_group`: the grandchild records its pid and sleeps 600 s; after the launcher timeout (now 5 s, so the grandchild starts on a loaded host) the test waits within the bounded deadline for that pid to vanish, fails explicitly if the grandchild never started, and kills a survivor before failing.
- `test_deepseek_harness_runtime.py` (two tests) and `test_requirement_intake.py::test_parent_recovery_serializes_with_child_link_and_preserves_reservation`: 5 s waits that must not expire use the bounded deadline.

All tasks in `tasks.md` are complete.

## Load proof

24 `yes > /dev/null` burners on 8 cores (load average 8.7 rising to 48), the eight affected tests run ten times in a row: 10/10 runs `8 passed`, 16–18 s each.

## Correctness and coherence

A genuine hang still fails within the bounded deadline with a diagnostic; no retry was added. Product code is untouched.

## Remainder (not in this slice)

- BR-768/T2 files, not touched: `test_lifecycle_workers.py::test_run_in_session_kills_the_whole_group_after_the_leader_exits` (asserts `< 1.4 s` and races a 1.5 s child sleep; high risk) and `test_writer_background_process_dies_with_it_and_tmpdir_is_dedicated` (1.5 s background sleep must outlast the group kill; medium).
- Pre-existing fallbacks in `tests/_concurrent_lifecycle.py`, not changed: an invalid `DEV_PLATFORM_TEST_PROCESS_TIMEOUT` silently falls back to the default, and a drain timeout after kill reports empty retained output.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence ...` on head 759120b0 passed: affected precheck, compileall, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all`.
