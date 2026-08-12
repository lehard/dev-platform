## ADDED Requirements

### Requirement: Fresh managed start is isolated from stale integration task state

A fresh managed task SHALL be distinguishable from resume of an existing managed task before first materialization. Task-specific state inherited from shared integration state SHALL NOT by itself establish the identity or resume status of the new task.

#### Scenario: Integration baseline contains stale task state

- **GIVEN** integration `main` exposes task state for managed task B
- **AND** managed task A has a valid central package but no repository-local canonical change yet
- **WHEN** task A starts through the managed intake path
- **THEN** the lifecycle treats A as a fresh task rather than a resume of A or B
- **AND** does not require canonical OpenSpec provenance for A before first materialization
- **AND** does not adopt source Issue B as A's identity

#### Scenario: Existing task is genuinely resumed

- **GIVEN** task A has an existing task worktree/branch with task-local identity and matching active or archived canonical provenance
- **WHEN** task A is resumed
- **THEN** the existing resume provenance guards remain authoritative
- **AND** the transport package is not re-applied over the canonical repository-local change

#### Scenario: Integration state belongs to another task during fresh start

- **WHEN** fresh task A observes integration-visible managed state for task B
- **THEN** that state is treated as contamination or non-authoritative integration evidence
- **AND** task A either materializes safely using its exact package identity or enters an explicit bounded recovery path
- **AND** the lifecycle does not guess or silently rewrite either task identity

### Requirement: Managed task-specific state does not become shared authoritative identity

Task-specific lifecycle state SHALL be scoped or cleaned so that completion of one managed task cannot make the next task checkout inherit that task as authoritative identity. The implementation MAY choose storage locality, cleanup, or explicit classification semantics, but SHALL preserve deterministic resume and recovery behavior.

#### Scenario: Managed task completes and another task starts

- **GIVEN** task B has reached terminal delivery
- **WHEN** later task A starts from the current integration baseline
- **THEN** task B's task-specific state cannot cause task A to enter resume-only provenance validation
- **AND** task A resolves identity from its own package/task evidence

#### Scenario: Existing contaminated baseline needs recovery

- **GIVEN** integration state already contains stale task-specific identity from a terminal task
- **WHEN** an operator starts the intended next managed task
- **THEN** the platform provides or documents a bounded recovery path that verifies the stale identity and preserves the new task's exact package identity
- **AND** recovery is idempotent
- **AND** recovery does not become a generic provenance-guard bypass

### Requirement: Terminal managed identity remains bound to the executing task

After a managed task is materialized, the platform SHALL preserve enough task-local identity to attribute all later managed side effects to that exact task. Repository or integration state belonging to another managed task SHALL NOT replace the executing task's source Issue or canonical change identity.

#### Scenario: Integration checkout contains stale task state

- **GIVEN** task A has matching task-local managed provenance
- **AND** the integration checkout exposes a state marker or package for task B
- **WHEN** task A reaches publication or terminal reconciliation
- **THEN** task A remains attributed to source Issue A
- **AND** Issue B is not selected or mutated as a substitute

#### Scenario: Multiple archived managed packages exist

- **GIVEN** the repository contains archived packages for several completed managed tasks
- **WHEN** one exact task resumes only terminal delivery/reconciliation
- **THEN** the lifecycle resolves the source identity belonging to that task's provenance/delivery
- **AND** does not select another archive merely because it is visible from integration main

#### Scenario: Task and integration identity disagree

- **WHEN** authoritative task-local identity disagrees with integration-visible managed state
- **THEN** the platform reports an explicit provenance mismatch
- **AND** blocks managed side-effect mutation until the mismatch is resolved
- **AND** does not guess which Development Backlog Issue should be updated

#### Scenario: Quick task has no managed source

- **WHEN** an ordinary quick task reaches terminal delivery without managed provenance
- **THEN** no Development Backlog managed identity is invented
- **AND** managed Project-status reconciliation remains a no-op for that task
