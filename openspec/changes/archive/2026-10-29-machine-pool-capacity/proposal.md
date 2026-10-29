## Why

On the owner's Mac the pool admitted runs while swap was at 9.6 of 10 GB: on macOS "available memory" is `vm_stat` free + inactive + speculative pages, which does not see real memory pressure. With the default run weight (`min(4, cpus - 1)` = 4) and `tokens = 6` only one heavy run fits and two tokens stay idle without any signal, and a docs-only selection also leases 4 tokens. The waiting line starts with "waiting for 4 of 6 token(s)" even when the tokens are free and the load check is what blocks, so agents reported "waiting for tokens" to the owner.

## What Changes

- macOS admission additionally waits while `kern.memorystatus_vm_pressure_level` is above normal (warn or critical); an unreadable or unknown value fails explicitly. The `vm_stat` available-memory check and Linux `MemAvailable` stay.
- The waiting line and `status` name the actual blocker first (queue, load, memory, memory pressure, tokens, admission lock) with its current value and threshold, then the needed and free tokens, the queue position and the holders. `status` adds the head waiter's blocker and keeps the `DEV_PLATFORM_MACHINE_POOL` prefix.
- `select_checks.py --execute` leases one token when every selected command is explicitly labelled with a non-test evidence type (`configuration`, `syntax`) and no affected-test precheck runs; otherwise, as today, the test parallelism bounded by `tokens`. Unlabelled commands count as heavy.
- `status` prints the effective run weight in the caller's environment (`DEV_PLATFORM_TEST_JOBS` or the automatic cap, bounded by `tokens`), how many such runs fit, and the idle tokens, with an explicit warning when `tokens` is not a multiple of the weight.
- The pool section of the workflow docs gains sizing guidance (tokens = concurrent runs × weight, weight via `DEV_PLATFORM_TEST_JOBS`, cores, memory reserved for VMs such as Docker Desktop, load limit) and states how participants on different releases interoperate.
- No pool configuration key, slot, ticket or lease format changes, so older releases that share the machine-local TOML keep working.

## Impact

- `template/scripts/machine_pool.py`, `template/scripts/select_checks.py`, `docs/engineering/agent-workflow.md`, `template/docs/engineering/agent-workflow.md.jinja`, `template/dev-platform/platform-manifest.json`.
- Tests: `tests/test_machine_pool.py` and the selected-check lease tests.
- Machine-local (owner's Mac, on the coordinator's signal only): `/Users/Shared/dev-platform-pool.toml` thresholds and `DEV_PLATFORM_TEST_JOBS=3` in `~/.bash_profile`, with rollback reported.
