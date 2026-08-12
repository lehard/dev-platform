# Tasks

## 1. Preflight against dependency

- [x] 1.1 Confirm `lehard/development-backlog#23` is complete and its changes are present in target `main`.
- [x] 1.2 Inspect the final `worktree-coordination` spec/implementation from #23 and map this change onto its canonical identity, normalization and machine-local coordination primitives.
- [x] 1.3 Reconcile any repository evolution since `prepared_against` without weakening the accepted hard/soft overlap and resume contract.

## 2. Admission contract and coordination

- [x] 2.1 Extend the existing coordination model with deterministic hard versus soft overlap classification and factual-scope precedence.
- [x] 2.2 Implement race-safe concrete-path read-and-claim semantics in the existing machine-local coordination state.
- [x] 2.3 Ensure completed/invalid task ownership no longer blocks future admission and diagnostics remain bounded/privacy-preserving.

## 3. Lifecycle integration

- [x] 3.1 Gate platform-owned `multi-agent` execution before first implementation changes while allowing planning/materialization preflight when needed for exact scope.
- [x] 3.2 Preserve and reuse an existing managed worktree/canonical OpenSpec on `WAIT`; do not duplicate worktrees or re-import the transport package on resume.
- [x] 3.3 Reconcile managed hard-overlap waiting to `Blocked` with actionable conflict context and successful resume to `In progress`.
- [x] 3.4 Preserve existing managed-task intake/materialization, Project reconciliation, agent-board cleanup and `standard`/`light` behavior.

## 4. Verification

- [x] 4.1 Add tests for exact hard overlap, directory/subsystem soft overlap and factual-scope precedence.
- [x] 4.2 Add a concurrency test proving two simultaneous claims for one concrete free path cannot both receive `RUN`.
- [x] 4.3 Add managed lifecycle tests for `WAIT`, `Blocked -> In progress`, repeated `WAIT`, and reuse of the same worktree/OpenSpec.
- [x] 4.4 Add regression coverage for claim release/stale ownership and independent parallel tasks.
- [x] 4.5 Run strict OpenSpec validation, relevant lifecycle/coordination tests and template/Copier smoke checks.
