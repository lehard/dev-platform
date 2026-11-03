## ADDED Requirements

### Requirement: Delivered child housekeeping does not stop the next child

Before advance starts a child, it SHALL archive task-local state of a Done child when local main equals origin/main and the child's archived contract is on it. Any other conflicting state SHALL still refuse with the reason. Without the coordinator queue, a missing or stale Requirement retrospective SHALL be returned as await-requirement-retrospective with the exact command; an unreadable or malformed receipt SHALL fail.

#### Scenario: Leftover state of a delivered child
- **WHEN** the checkout holds the state of a Done child and local main equals origin/main
- **THEN** advance archives the state and starts the next child

#### Scenario: Retrospective not yet recorded
- **WHEN** every child is delivered and the retrospective receipt is missing
- **THEN** advance returns await-requirement-retrospective with the checkpoint command and exits 0

#### Scenario: Malformed retrospective receipt
- **WHEN** the receipt exists but is malformed
- **THEN** advance fails naming the problem
