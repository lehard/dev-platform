# shared-workspace-coordination Specification Delta

## ADDED Requirements

### Requirement: An agent raises an explicit owner-needed signal for its own task

The platform SHALL let an agent working in a registered task raise one owner-needed signal carrying the question text, the project and the task, and SHALL store it with that task's agent-board entry under the board's existing lock. A signal SHALL be accepted only for an active board entry of the caller's own worktree. A missing board capability, board file, active entry or question SHALL fail with an explicit error naming the cause, and no default task SHALL be assumed. A signal SHALL end with its task's board entry. The signal SHALL report a question only; it SHALL NOT decide or answer anything.

#### Scenario: Agent raises a signal
- **GIVEN** a task registered on the board whose worktree the agent is in
- **WHEN** the agent raises a signal with a question
- **THEN** an open signal with the question, project and task is stored on that board entry

#### Scenario: Missing or foreign task is rejected
- **WHEN** a signal is raised from a worktree with no active board entry, or for another worktree's task
- **THEN** the command fails with an error naming the cause
- **AND** nothing is stored

### Requirement: Repeated signals collapse and a resolved question is cleared

A signal's identity SHALL be its task plus the normalised question text. Raising an open signal again SHALL NOT create a second record and SHALL refresh its last-raised time. Resolving a signal SHALL record who resolved it and when, and a resolved signal SHALL no longer be shown as open. Raising the same text after resolution SHALL open a new signal. Resolving an unknown or already resolved signal SHALL fail explicitly.

#### Scenario: Repeat does not multiply
- **GIVEN** an open signal for a question
- **WHEN** the same question is raised again for the same task
- **THEN** there is still one open signal with a refreshed last-raised time

#### Scenario: Resolved question is cleared
- **WHEN** the signal is resolved
- **THEN** it is not shown as open
- **AND** raising the same question again opens a new signal
