## ADDED Requirements

### Requirement: Stale managed tasks have a supported non-rewriting reconcile path

The platform SHALL provide an explicit managed-task reconciliation operation for a task branch that no longer contains current authoritative main. The operation SHALL reuse existing managed provenance, freshness and publication state, SHALL preserve protected-main and exact-head safeguards, and SHALL NOT require force-push or automatic history rewrite.

#### Scenario: Unpublished task falls behind main

- **GIVEN** a managed task branch has not yet been published
- **AND** authoritative `origin/main` has advanced
- **WHEN** the operator invokes the supported reconcile operation
- **THEN** the platform safely incorporates current main using a non-destructive history-preserving update
- **AND** the task can proceed through the normal freshness and validation gates

#### Scenario: Exact managed PR is already open

- **GIVEN** the task has an open exact managed PR
- **AND** target main advances after publication
- **WHEN** reconciliation is requested
- **THEN** the platform preserves task/PR ancestry so the updated task head can be fast-forward pushed to the same PR branch
- **AND** it does not rebase the published branch or require force-push

#### Scenario: Task worktree is dirty

- **WHEN** safe reconciliation would require automatically stashing, resetting or otherwise hiding dirty task work
- **THEN** the platform stops with an actionable blocker
- **AND** leaves the dirty work untouched

#### Scenario: Reconciliation conflicts

- **WHEN** current main cannot be incorporated without a merge conflict
- **THEN** the operation stops before publication
- **AND** reports the conflicting repository-relative paths
- **AND** does not guess a resolution

### Requirement: Freshness drift is visible before another expensive validation run

Supported task status/preflight SHALL expose when the current managed task head is behind authoritative main before the platform begins a new expensive authoritative validation cycle. A stale observation SHALL remain resumable rather than being reported as terminal task failure.

#### Scenario: Main advanced after prior task work

- **GIVEN** a managed task was previously valid
- **AND** authoritative main advances while the task remains active
- **WHEN** the operator asks for task status or begins the finish path
- **THEN** the platform reports that reconciliation is required before expensive validation
- **AND** points to the supported reconcile operation

### Requirement: Reconciliation preserves validation and publication authority

A successful reconcile SHALL create a new task head that must satisfy the current required validation and exact-head publication lifecycle. Reconciliation SHALL NOT reuse stale validation evidence as if it applied to the new head and SHALL NOT create a second publication path.

#### Scenario: Reconciled task resumes delivery

- **GIVEN** reconciliation completed successfully
- **WHEN** delivery resumes
- **THEN** current required checks run for the reconciled head
- **AND** publication continues through the existing exact-head PR/recovery mechanism
- **AND** a repeated reconcile on an already-current head is a no-op
