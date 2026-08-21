## ADDED Requirements

### Requirement: Standard profile exposes a managed task-start compatibility contract

Dev Platform SHALL provide the callable task-start interface required by
managed-task intake for every supported standard-profile generated or adopted
project. The interface SHALL create/reuse only the configured isolated task
clone/branch and SHALL preserve existing profile-specific lifecycle behavior.

#### Scenario: Managed intake starts a standard-profile task

- **GIVEN** a structurally valid managed package targets a standard-profile project
- **WHEN** managed start composes package intake with the project task-start entrypoint
- **THEN** the callable task-start contract is available and creates the expected isolated task state
- **AND** package materialization occurs only in that task checkout.

#### Scenario: Template removes a required start interface

- **WHEN** a platform template or shared helper no longer satisfies the managed intake task-start contract
- **THEN** deterministic platform compatibility tests fail before release or downstream rollout
- **AND** no downstream project must discover the mismatch during implementation.

### Requirement: Standard parent-only routing supports isolated full clones without weakening child containment

Dev Platform SHALL permit routing preflight for a parent-only standard-profile
task executed in an isolated full clone. It SHALL record that clone as the
parent route root without requiring a multi-agent linked worktree.

This exception SHALL NOT authorize a delegated child writer. A child that can
write repository state SHALL continue to require an assigned worktree and the
existing proven containment boundary.

#### Scenario: Supervisor records standard-clone preflight

- **GIVEN** a managed standard-profile task runs in a standalone isolated clone
- **WHEN** the supervisor records routing preflight
- **THEN** routing succeeds with the clone as the parent route root
- **AND** the record truthfully identifies parent-only execution.

#### Scenario: Child writer is requested from a standard clone

- **WHEN** a write-capable delegated child is requested without a distinct assigned worktree
- **THEN** the platform refuses the launch before the child can write
- **AND** parent-only route recording is not treated as child containment evidence.

### Requirement: Platform release validates downstream profile compatibility

Dev Platform SHALL run a deterministic consumer compatibility suite for light,
standard and multi-agent profiles before publishing or rolling out template
lifecycle changes. The suite SHALL include standard managed-start and routing
preflight behavior through rendered or adopted downstream-compatible files.

#### Scenario: Standard consumer canary fails

- **WHEN** the rendered/adopted standard-profile canary cannot complete managed-start composition or routing preflight
- **THEN** platform release or rollout validation fails before downstream publication
- **AND** the diagnostic identifies the profile and lifecycle boundary that failed.

#### Scenario: Profile controls remain compatible

- **WHEN** the consumer compatibility suite runs
- **THEN** light and multi-agent profile controls continue to pass their supported lifecycle contracts
- **AND** the suite does not require real GitHub credentials, a model runtime, or a write-capable child agent.
