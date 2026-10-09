## 1. Pool module

- [x] 1.1 Implement `template/scripts/machine_pool.py` (config validation, slots, queue, priority, load admission, bounded wait, nesting, status) and the `scripts/` source adapter shim.

## 2. Integration

- [x] 2.1 Acquire in `select_checks.execute`, `run_test_groups.main` (non-nested, jobs bounded by lease) and Requirement full-candidate validation; set `finalize` class for finalization and integration runs.

## 3. Evidence and delivery

- [x] 3.1 Add unit and multi-process regression tests and register them in `dev-platform/checks.toml`.
- [x] 3.2 Document configuration, directory setup, status and failure modes in `docs/engineering/agent-workflow.md` and its template copy.
- [ ] 3.3 Run required platform checks, record truthful verification, archive, retrospectives and publication.
