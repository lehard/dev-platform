## 1. Scope gate

- [x] 1.1 Add the explicit-mode helper and make `hard_scope_conflicts`/`enforce_scope_gate` raise on every unmet precondition when the capability is on; keep the documented non-gate when off.
- [x] 1.2 Remove the `agent_board` stand-ins from `select_checks.py` and `finish_task.py`; read `main_branch` without a default in protected/coordinator checks; add `select_checks.py --scope-gate {enforce,not-applicable}` (default `enforce`; coordinator base modes imply not-applicable) and pass `not-applicable` in the CI workflows.

## 2. Publication gates

- [x] 2.1 Add the three-valued ancestry helper in `publication_queue.py` and use it at every `--is-ancestor` site.
- [x] 2.2 Classify every `_latest(...) or {}` site; raise on a missing superseded-head lineage record; record the classification in `design.md`.
- [x] 2.3 Make `candidate_lifecycle.first_record`/`latest_record` raise on a malformed trusted record.
- [x] 2.4 Make `delegation_containment.verify_remote_fast_forward` raise on config or git failure and read `main_branch` without a default.

## 3. Verification and integration

- [x] 3.1 Make `run_test_groups.resolve_jobs` reject an invalid `DEV_PLATFORM_TEST_JOBS`.
- [x] 3.2 Make `integration_state.serialized_integration` raise without `fcntl`; remove the `_platform_common` shared-workspace stand-ins.

## 4. Tests

- [x] 4.1 For each fixed site, a test that fails on the old behavior and passes on the new one; a test that a project with `agent_board = false` still runs the portable path.

## 5. Verification and delivery

- [ ] 5.1 Required platform checks, truthful semantic verification, archive, retrospectives, publication.
