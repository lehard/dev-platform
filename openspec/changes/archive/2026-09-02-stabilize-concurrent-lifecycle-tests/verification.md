# Verification: Stabilize concurrent lifecycle tests

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review (no `/opsx:verify` tool integration in this environment) plus full local platform test/validation run at the default and an explicit worker count

## Completeness

- All `tasks.md` items are complete; the final item is this verification/archive/publish step.
- The three added spec requirements are each covered:
  - *Concurrent lifecycle tests synchronize observable readiness* — `run_observed_delegation` gained an opt-in `ready_probe` / `ready_deadline` handshake; the cleanup test now synchronizes on the descendant pid before the steady-state timeout starts, and `test_delayed_child_startup_still_passes_the_readiness_handshake` / `test_child_that_never_becomes_ready_fails_with_diagnostics` cover the delayed and never-ready scenarios.
  - *Default test concurrency is bounded and overridable* — `run_test_groups.resolve_jobs()` caps automatically selected parallelism at `_DEFAULT_JOBS_CEILING` (4) and records `jobs`/`jobs_source` in aggregate evidence; an explicit `DEV_PLATFORM_TEST_JOBS` or `--jobs` is used verbatim (`DefaultParallelismTests`).
  - *Publication recovery timeouts remain bounded and diagnostic* — `tests/_concurrent_lifecycle.communicate_within_deadline` gives the publication-recovery concurrency tests one bounded deadline with a `DEV_PLATFORM_TEST_PROCESS_TIMEOUT` override that, on expiry, reports pid / returncode / retained output (`BoundedTestDeadlineHelperTests`).
- No overlap with other active changes: no other active `openspec/changes/<change>/` directory touches `delegated_write_guard.py`, `run_test_groups.py`, or these test modules.

## Correctness

- The readiness handshake only shifts when the steady-state `timeout` clock starts; it does not weaken it. A child that never becomes ready is reaped and raises `GuardedChildError` within `ready_deadline` (`test_child_that_never_becomes_ready_fails_with_diagnostics`), and the existing hung-process cases (`test_streaming_timeout_cleans_up_a_silent_writer`, `test_child_timeout_cancellation_still_runs_post_check`) are unchanged and still pass.
- `communicate_within_deadline` kills the helper and raises `HelperTimeout` (an `AssertionError`) with process identity and retained output on expiry; it does not retry. The dedicated product-timeout case `test_already_merged_reconciliation_still_times_out_for_a_hung_lock_holder` (product timeout `0.05`) is untouched and still proves a real hung lock holder fails fast.
- The parallelism cap is `min(ceiling, cpu_count-1)` and never drops below 1; an explicit positive `DEV_PLATFORM_TEST_JOBS`/`--jobs` bypasses the cap entirely. A non-positive `--jobs` is rejected with exit code 2.
- `ready_probe` / `ready_deadline` are optional keyword-only parameters defaulting to `None`; every existing caller of `run_observed_delegation` / `run_guarded_delegation` is unaffected. No production caller sets them.

## Coherence

- `template/scripts/*` changes are additive and backward-compatible, so the reusable downstream lifecycle (Copier render + update) is unaffected: new optional kwargs and a new internal ceiling constant only.
- The new `tests/_concurrent_lifecycle.py` helper is a single shared source for the outer test-process deadline; `test_pr_reconciliation_concurrency.py` now derives its `PROCESS_COMPLETION_TIMEOUT_SECONDS` and readiness wait from it, so there is one configurable timeout across the concurrency tests.
- `_concurrent_lifecycle.py` is prefixed with `_` and is not collected by `unittest discover`; `run_test_groups.py --verify-coverage` still reports declared == discovered (809 == 809, no gaps, no duplicates).
- No safety guard, containment rule, credential scope, merge behavior, or retry policy was introduced or modified.

## Acceptance evidence

Run locally in the task worktree on branch `agent/stabilize-concurrent-lifecycle-tests`:

- `python3 -m compileall -q template/scripts scripts` — OK
- `python3 scripts/managed_projects.py validate` — OK (3 managed, 7 candidate, 3 excluded)
- `python3 template/scripts/openspec_lifecycle.py check` — OK
- `openspec validate stabilize-concurrent-lifecycle-tests` — valid
- `python3 scripts/run_test_groups.py --all` — 809 tests, all 13 groups success; aggregate `jobs=4, jobs_source=auto-capped`
- `DEV_PLATFORM_TEST_JOBS=2 python3 scripts/run_test_groups.py --all` — 809 tests, all 13 groups success; aggregate `jobs=2, jobs_source=DEV_PLATFORM_TEST_JOBS`
- `test_timeout_reaps_writer_process_group_before_releasing_ownership`, `test_delayed_child_startup_still_passes_the_readiness_handshake`, `test_child_that_never_becomes_ready_fails_with_diagnostics` — repeated 3× consecutively, deterministic pass.

No release was cut and no rollout was executed. The `template/scripts` changes reach downstream projects only through the normal reviewed Copier rollout PR path once released.

## Findings

No material completeness, correctness or coherence findings remain.

Automated-Checks-Evidence: automated-checks.json
