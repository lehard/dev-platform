## 1. Admission and reporting

- [x] 1.1 `machine_pool.py`: macOS memory-pressure measurement through `kern.memorystatus_vm_pressure_level`, explicit error when unreadable or unknown; admission waits above normal.
- [x] 1.2 One blocker evaluation used by the waiting line and `status`: blocker kind, value and threshold first, then needed/free tokens, queue position, holders; `status` reports the head waiter's blocker.
- [x] 1.3 `status`: effective run weight in the caller's environment, runs that fit, idle tokens, warning when `tokens` is not a multiple of the weight.

## 2. Lease weight

- [x] 2.1 `select_checks.py --execute`: one token when every selected command is labelled `configuration` or `syntax` and no affected-test precheck runs; otherwise the test parallelism.

## 3. Documentation

- [x] 3.1 Pool section in `docs/engineering/agent-workflow.md` and its template: sizing guidance, memory pressure, blocker-first reporting, light-selection weight, mixed-release behaviour; regenerate the platform manifest.

## 4. Verification

- [x] 4.1 Regression tests: recorded `sysctl`/`vm_stat` outputs (pressure warn blocks naming memory, normal admits, unreadable fails); two default-weight runs admitted together on 6 tokens with weight 3; mismatch warning; "tokens free, load blocks" reads as load; light selection leases 1; unlabelled leases full weight; current-schema config stays valid.
- [x] 4.2 Measure the recommended configuration (6 tokens, weight 3 through `DEV_PLATFORM_TEST_JOBS=3` set only in the two measured run processes) with two concurrent heavy runs on the owner's Mac (backup of the pool file first); record the measurement, the thresholds chosen from it and the operator's persistent edits with their rollback in `verification.md`. Persistently applying them on the machine is an operator step outside this change.
- [x] 4.3 Full selected checks (on the coordinator's signal) and semantic OpenSpec verification.
