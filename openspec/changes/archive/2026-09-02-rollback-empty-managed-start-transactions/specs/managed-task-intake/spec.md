## ADDED Requirements

### Requirement: Empty managed-start transactions are recoverable without manual state editing

Dev Platform SHALL remove or supersede a managed-start transaction only after proving that the failed attempt created no task worktree, branch or board entry.

#### Scenario: Package validation fails before task state exists

- **WHEN** managed start creates a transaction and package validation fails before worktree, branch or board mutation
- **THEN** the exact empty transaction is removed during failure cleanup
- **AND** no task-side effect remains

#### Scenario: Corrected package retries after an empty failure

- **WHEN** a corrected package revision is retried against a stale transaction
- **AND** the exact worktree, branch and board entry are all absent
- **THEN** the stale transaction is safely superseded and normal start continues

#### Scenario: Partial state exists

- **WHEN** any matching or ambiguous worktree, branch or board state exists
- **THEN** automatic empty rollback is refused
- **AND** the existing conservative recovery diagnostics are preserved
