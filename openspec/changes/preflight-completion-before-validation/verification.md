# Verification

OpenSpec-Verify: PENDING
Verification-Method: Executor automated checks only; semantic OpenSpec review is deferred to the supervisor (tasks.md item 7).

## Scope of this receipt

This records the automated validation actually executed by the managed-task
executor after implementing the two ADDED requirements in
`specs/completion-lifecycle/spec.md`. It does not assert a semantic PASS.

## Implementation summary

- `template/scripts/finish_task.py`
  - New `observe_completion_blockers(...)` performs only read-only observations
    and returns `(stage_label, detail)` pairs for every independently observable
    blocker: OpenSpec/provenance hygiene, friction checkpoint, worktree
    cleanliness, task freshness, branch-base staleness (PR mode, no exact-head
    open PR), and hard scope overlap (`enforce_scope_gate`, non-mutating).
  - `main()` calls it once, immediately before `run_checks`, after the existing
    `warn_current_worktree_scope_overlap` advisory. Any blockers are printed as
    one bounded report and `SystemExit(1)` is raised before expensive validation.
  - The `task_pr_is_already_merged` early-return recovery path and
    `fetch_main(...)` still precede the aggregation.
  - `run_openspec_hygiene` now returns `str | None` (keeps the
    `record_lifecycle_friction` side effect); `run_friction_retry_and_checkpoint`
    is split into best-effort `run_friction_route_pending_retry` and
    blocking `observe_friction_checkpoint_blocker`.
  - The immediately-before-publication rechecks (`enforce_scope_gate` +
    `block_for_scope_conflict`, `resume_from_scope_conflict`, PR stale-base
    guard) are unchanged.
  - `run_checks` now streams the child's combined output line-by-line via
    `subprocess.Popen` while accumulating full text for
    `validation_failure_evidence`; return/raise semantics are unchanged.
  - `emit_finish_stage(...)` prints one flushed `DEV_PLATFORM_FINISH_STAGE:`
    line at preflight start, preflight-clear, validation-clear, and completion.
- `template/scripts/run_test_groups.py` emits a flushed
  `DEV_PLATFORM_TEST_GROUP_START:` line as each parallel group is dispatched
  and each serial group begins (no new threads or polling).

## Executed checks (task worktree)

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 scripts/run_test_groups.py --all` — success, 13/13 groups, 0 failed
  (`DEV_PLATFORM_TEST_AGGREGATE ... "outcome": "success"`)
- `python3 template/scripts/openspec_lifecycle.py check` — OpenSpec lifecycle hygiene: OK
- `openspec validate preflight-completion-before-validation --strict` — valid

## Added regressions (tests/test_git_lifecycle.py)

- `test_preflight_hard_scope_overlap_blocks_before_expensive_validation` — a
  known hard overlap blocks finish with real `run_checks`; `DEV_PLATFORM_CHECK_COMMAND`
  and the costly sentinel are absent, `preflight clear` stage is not emitted.
- `test_preflight_reports_two_independent_blockers_in_one_invocation` — dirty
  worktree + hard scope overlap are both reported in one finish
  (`Completion preflight found 2 blocker(s)`), no costly command runs.
- `test_clean_preflight_streams_stage_and_validation_progress_then_publishes` —
  a clean preflight runs real checks, publishes, and stdout carries the four
  ordered `DEV_PLATFORM_FINISH_STAGE` markers with validation output interleaved
  between preflight-clear and validation-clear.
- `test_run_checks_streams_child_output_incrementally` — `run_checks` forwards
  the first child line within 1s while the child keeps running ~2s more.
