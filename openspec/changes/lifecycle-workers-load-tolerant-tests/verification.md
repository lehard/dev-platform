OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review of the test diff against the platform-ci delta, proposal, design and tasks; ten repeated runs of the two tests under artificial CPU oversubscription; repository-owned selected checks (full set) on the committed candidate head
Automated-Checks-Evidence: automated-checks.json

## Scope

Slice 2 of Requirement BR-812: the remainder recorded after T1 (#823, PR lehard/dev-platform#738). Test-only; `lifecycle_workers.py` is unchanged.

## Completeness

- `test_run_in_session_kills_the_whole_group_after_the_leader_exits`: both background children (closed pipes and stdout holder) record their pid atomically and sleep 600 s before their late write; the leader prints only after both pids exist. `run_in_session` runs with `timeout=process_deadline_seconds()`, so a stdout holder that kept it waiting raises `TimeoutExpired` instead of the former `< 1.4 s` bound. `assert_processes_gone` checks both pids vanish within the bounded deadline; the late markers stay absent.
- `test_writer_background_process_dies_with_it_and_tmpdir_is_dedicated`: the fake writer's `sleeper` mode starts the same pid-recording 600 s child and exits only once it is live; the test checks that pid is gone and the hook mark absent, instead of `time.sleep(2.5)` against a 1.5 s child sleep.
- A child that never records its pid or survives the deadline fails explicitly naming it (the survivor is killed first); no retry.

All tasks in `tasks.md` are complete.

## Load proof

24 `yes > /dev/null` burners on 8 cores (load average rising to 32): the two tests ran ten times in a row, 10/10 `2 passed`.

## Selected checks

`python3 scripts/select_checks.py --base origin/main --execute --evidence ...` on head 3b8b35c1 passed: compileall, ruff, `generate_platform_manifest.py --check`, `run_test_groups.py --all`.
