## MODIFIED Requirements

### Requirement: Managed intake proves the live agent session can safely create shared artifacts

Before any supported managed intake path creates or reuses a task worktree, materializes a managed OpenSpec package, or changes a Development Backlog Project item, the platform SHALL run a disposable self-test of the live execution under the shared-workspace root.

#### Scenario: A Codex or Claude session lacks the required creation behavior

- **WHEN** the session self-test cannot create or publish a required conforming
  probe artifact
- **THEN** intake fails without creating a task worktree or branch,
  materializing package files, or changing Project state
- **AND THEN** the diagnostic identifies the session-level fact that failed and
  tells the user to correct the launcher/session and restart or re-login only
  when that can address the failure

### Requirement: An agent raises an explicit owner-needed signal for its own task

The platform SHALL let an agent working in a registered task raise one owner-needed signal carrying the question text, the project and the task, and SHALL store it with that task's agent-board entry under the board's existing lock.

#### Scenario: Agent raises a signal
- **GIVEN** a task registered on the board whose worktree the agent is in
- **WHEN** the agent raises a signal with a question
- **THEN** an open signal with the question, project and task is stored on that board entry

#### Scenario: Missing or foreign task is rejected
- **WHEN** a signal is raised from a worktree with no active board entry, or for another worktree's task
- **THEN** the command fails with an error naming the cause
- **AND** nothing is stored

## ADDED Requirements

### Requirement: The managed intake self-test proves shared group membership and conforming creation

The managed intake self-test SHALL prove effective membership in the required shared group and actual creation of a group-writable file, a group-writable setgid directory and an atomically replaced file that each satisfy the shared-workspace contract.

#### Scenario: Self-test proves session capabilities

- **WHEN** the managed intake self-test runs
- **THEN** it proves effective membership in the required shared group
- **AND** it proves actual creation of a group-writable file, a group-writable setgid directory and an atomically replaced file that each satisfy the shared-workspace contract

### Requirement: The managed intake self-test removes only its own probe directory

The managed intake self-test SHALL remove only its uniquely created probe directory.

#### Scenario: Self-test cleans up

- **WHEN** the managed intake self-test finishes
- **THEN** it removes only its uniquely created probe directory

### Requirement: An owner-needed signal is accepted only for the caller's own active entry

An owner-needed signal SHALL be accepted only for an active board entry of the caller's own worktree.

#### Scenario: Signal for the caller's own active entry

- **WHEN** an owner-needed signal is raised
- **THEN** it is accepted only for an active board entry of the caller's own worktree

### Requirement: A missing owner-needed signal precondition fails explicitly

A missing board capability, board file, active entry or question SHALL fail with an explicit error naming the cause, and no default task SHALL be assumed.

#### Scenario: Signal precondition is missing

- **WHEN** an owner-needed signal is raised with a missing board capability, board file, active entry or question
- **THEN** it fails with an explicit error naming the cause
- **AND** no default task is assumed

### Requirement: An owner-needed signal ends with its task's board entry

An owner-needed signal SHALL end with its task's board entry.

#### Scenario: Board entry ends

- **GIVEN** an owner-needed signal stored on a task's board entry
- **WHEN** that board entry ends
- **THEN** the signal ends with it

### Requirement: An owner-needed signal only reports a question

The owner-needed signal SHALL report a question only; it SHALL NOT decide or answer anything.

#### Scenario: Signal is raised

- **WHEN** an owner-needed signal is raised
- **THEN** it reports a question only
- **AND** it does not decide or answer anything
