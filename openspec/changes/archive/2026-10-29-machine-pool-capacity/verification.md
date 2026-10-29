OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the platform-lifecycle delta, proposal, design and tasks; targeted unit tests; `openspec validate --strict`; repository-owned selected checks recorded by the lifecycle; on-machine measurement of two concurrent heavy runs on the owner's Mac
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Owner (BR-730, 2026-10-21): two heavy runs of 3 workers on 6 tokens for this Mac; thresholds chosen by the executor from measurement.
- ADD (no open choice): run weight through `DEV_PLATFORM_TEST_JOBS`, not a new pool key, because pooled older releases on the same machine reject unknown keys; macOS memory signal is the kernel pressure level, not the swap ratio; a weight that does not divide the tokens is a `status` warning, not a refusal.
- Coordinator 2026-10-29 (variant B): the auto mode classifier refused the persistent `~/.bash_profile` edit, so the measurement ran with `DEV_PLATFORM_TEST_JOBS=3` set only in the two measured run processes, and the persistent application is an operator step (below).

## Completeness

- macOS memory pressure: `parse_memory_pressure_level` (1/2/4, unknown and non-integer fail), `measure_memory_pressure` (sysctl call, non-zero exit fails, Linux `None`, other platforms fail); admission waits at warn and fails when unmeasurable (`test_memory_pressure_above_normal_waits_naming_memory_and_unmeasurable_pressure_fails`); the incident shape from a recorded `vm_stat` plus pressure output (`test_nearly_exhausted_swap_with_plenty_of_inactive_pages_is_blocked_by_pressure`).
- Blocker first: `test_free_tokens_with_a_load_blocker_read_as_load_not_tokens`; the existing timeout, queue and progress tests now read the blocker-first wording; `status` head-waiter blocker (`test_head_waiter_blocker_is_named_with_free_tokens`).
- No idle tokens: `test_two_runs_of_weight_three_share_six_tokens_with_none_idle`; `status` weight lines and warning (`StatusWeightTests`); an invalid `DEV_PLATFORM_TEST_JOBS` fails in `status`.
- Light selection: `test_select_checks_light_selection_leases_one_token_and_others_the_test_parallelism` (labelled light leases 1; a `test`, unlabelled or precheck selection leases the test parallelism; end to end `acquired 1 of 3`).
- Compatibility: `test_current_schema_configuration_stays_valid` (the five keys stay the whole schema); slot, ticket and lease formats are unchanged in the diff.
- Docs: pool section in `docs/engineering/agent-workflow.md` and its template (pressure, blocker-first, light selection, sizing, mixed releases).

## Correctness

- The only machine consumer of the waiting lines (`post_review_finalization`) filters by the unchanged `DEV_PLATFORM_MACHINE_POOL` prefix.
- `resolve_jobs` gains an optional mapping argument; existing callers pass nothing and keep reading `os.environ`.
- Requirement full-candidate validation keeps leasing the test parallelism (not touched).

## Coherence

- Spec delta, design and docs describe the same three admission signals, the same light-selection rule and the same `status` lines.

## On-machine measurement (2026-10-29 02:35–03:11, owner's Mac: 4 physical / 8 logical cores, 16 GB)

- Run A: `select_checks.py --base origin/main --execute --evidence ...` in the task worktree; run B: `run_test_groups.py --all` in a separate clone of the same commit; both with `DEV_PLATFORM_TEST_JOBS=3`, pool file unchanged (`tokens = 6`, `max_load_per_cpu = 2.5`, `min_available_memory_mb = 2048`).
- Both acquired `3 of 6 token(s)` after 0 s; `status` showed `tokens: 6 (held 6, free 0)` with both holders at weight 3.
- 71 samples every 30 s: 60 with all 6 tokens held, 7 with 3 (one run finishing), 4 with none (start and end); no sample had free tokens while a run waited.
- During the 60 full samples: memory pressure level 1 (normal) throughout, kernel free 69–71 %; swap used 324–356 MB of a 1024 MB allocation; `vm_stat` available 5721–5904 MB; load average 4.7–21.0 (median 12.8), load per CPU 0.59–2.65 (median 1.60).
- Both runs passed (run B: 18 groups, `jobs 3`, 4062 group-seconds; run A: all five selected commands, test groups in 1611 s).
- The status sampler, run without `DEV_PLATFORM_TEST_JOBS`, printed the mismatch warning for the automatic weight 4 on 6 tokens, as designed.
- Limit: memory pressure never left normal, so the warn path is proven by tests on recorded output, not by this run.

## Thresholds

- `max_load_per_cpu = 2.5` stays: two concurrent runs peaked at 2.65 and a run is only admitted at its start, when at most one other run is active (median about half of the two-run load), so 2.5 admits the second run and still stops admission under an overloaded machine such as the observed 40 per CPU.
- `min_available_memory_mb = 2048` stays: two runs lowered `vm_stat` available memory by under 200 MB and pressure stayed normal; the Docker VM allocation is already outside the available figure, and memory pressure is now the primary memory guard.
- So the pool file needs no edit; the backup `/Users/Shared/dev-platform-pool.toml.bak-br730` equals the current file.

## Operator step (persistent application, not done by this change)

- Add after the `DEV_PLATFORM_MACHINE_POOL` line in `~/.bash_profile`:
  `export DEV_PLATFORM_TEST_JOBS=3  # BR-730: 2 heavy runs x 3 workers on 6 tokens`
- Rollback: delete that line. The pool file stays as it is; if it is ever changed, restore it from the backup.
- The Requirement acceptance "applied on this Mac" stays open until this line is in place and `machine_pool.py status` prints `heavy-run weight: 3 (DEV_PLATFORM_TEST_JOBS); 2 concurrent run(s) fit, 0 token(s) idle`.

## Noticed, not changed

- `run_test_groups.resolve_jobs` uses `os.cpu_count() or 2` when the CPU count is unknown (an existing default, outside this slice).
- `orchestrate_pre_authoring.py` documents `handoff/<intent-or-group>.json` but reads only per-intent envelopes (friction recorded).
