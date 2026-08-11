## ADDED Requirements

### Requirement: Managed task start preserves integration-copy isolation

For a platform-owned feature-capable workflow, managed task start SHALL
perform package discovery and target validation without materializing files,
synchronize the integration branch, create the configured task branch or
worktree, and materialize the OpenSpec package only in that task checkout.
The integration copy SHALL remain clean after a successful managed task start.

#### Scenario: Multi-agent managed task starts successfully

- **GIVEN** a clean integration copy and a valid managed backlog package
- **WHEN** the platform starts the managed task
- **THEN** it creates and registers an isolated task worktree before materializing the OpenSpec package
- **AND** all imported OpenSpec artifacts exist in that task worktree
- **AND** the integration copy remains clean on its integration branch

#### Scenario: Standard managed task starts successfully

- **GIVEN** a clean integration copy and a valid managed backlog package
- **WHEN** the platform starts the managed task in the `standard` profile
- **THEN** it creates the task feature branch before materializing the OpenSpec package
- **AND** the imported artifacts belong to that feature branch rather than the integration branch

#### Scenario: Managed package is invalid before task creation

- **GIVEN** the supplied issue does not contain a valid package for the current repository
- **WHEN** managed task start performs read-only package discovery
- **THEN** it refuses before creating a branch, worktree, board entry or OpenSpec files

#### Scenario: Materialization fails after task creation

- **GIVEN** a task branch or worktree has been created for a valid managed package
- **WHEN** materialization or strict OpenSpec validation fails
- **THEN** the platform reports the failure without modifying the integration copy
- **AND** it reconciles the newly created local task state without deleting unrelated work

### Requirement: Direct managed import protects feature-capable integration branches

The standalone managed importer SHALL refuse to materialize a package from the
integration branch of a platform-owned `standard` or `multi-agent` workflow.
The error SHALL direct the caller to the managed task start entrypoint. Direct
materialization remains supported where the `light` profile intentionally
performs work on its integration branch.

#### Scenario: Importer is invoked from multi-agent integration main

- **GIVEN** a platform-owned `multi-agent` workflow is on its integration branch
- **WHEN** a caller invokes the standalone managed importer
- **THEN** it fails before creating OpenSpec artifacts
- **AND** it explains how to start the managed task in an isolated worktree

#### Scenario: Importer is invoked from a standard task branch

- **GIVEN** a platform-owned `standard` workflow is on a task feature branch
- **WHEN** a caller invokes the standalone managed importer
- **THEN** it may materialize the package in that feature branch

#### Scenario: Importer is invoked in the light profile

- **GIVEN** a platform-owned `light` workflow is on its integration branch
- **WHEN** a caller invokes the standalone managed importer
- **THEN** it may materialize the package according to the light workflow

## MODIFIED Requirements

### Requirement: Task intake preserves managed and quick execution paths

The platform lifecycle SHALL distinguish planned managed work from small direct
quick work before implementation begins. A Development Backlog issue explicitly
supplied as the task source SHALL use managed-task intake and OpenSpec
preflight. For platform-owned feature-capable profiles, managed-task intake
SHALL first establish the task branch or worktree and then materialize the
referenced OpenSpec planning contract in that task checkout. A small task
directly requested by the user MAY enter the existing execution lifecycle
without first creating a central backlog issue or ceremonial OpenSpec.

#### Scenario: User explicitly supplies a managed backlog task

- **WHEN** the user asks the agent to take a supported Development Backlog issue
- **THEN** the agent uses managed-task intake to discover and verify the referenced OpenSpec planning contract before implementation
- **AND** the platform materializes that contract only after the configured task branch or worktree is established
- **AND** does not ask the user to restate the already captured product decision

#### Scenario: User gives a small direct fix

- **WHEN** the requested work is a small scoped change that does not require a product/architecture contract
- **THEN** the agent may use the existing task start/check/finish workflow directly
- **AND** does not create a central Development Backlog issue solely to record short-lived work

#### Scenario: Quick task becomes non-trivial

- **WHEN** implementation reveals that a quick task requires a material behavior, architecture, compatibility, data-contract or scope change
- **THEN** the agent stops before knowingly broadening the contract
- **AND** proposes escalation to a managed task/OpenSpec instead of silently continuing as a quick fix
