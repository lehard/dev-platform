## ADDED Requirements

### Requirement: Verified technical child project routing

Dev Platform SHALL derive technical-child routing from the exact parent Requirement's single `project:*` label and Backlog repository together with the committed target `[development_backlog]` configuration, SHALL reject any contradiction, missing or ambiguous routing input before an Issue is created, and SHALL report materialization success only after read-back proves the child's exact `project:*` label, `type:internal-change` label and parent link. The platform SHALL NOT silently relabel a contradictory child.

#### Scenario: Consistent routing

- **WHEN** the parent Requirement label, its Backlog repository and the committed configuration identify the same project
- **THEN** the child is created or exactly reused with that `project:*` label
- **AND** success is reported only after read-back shows `project:*`, `type:internal-change` and the parent link

#### Scenario: Conflicting routing is rejected before publication

- **WHEN** the committed `project_label` or Backlog repository differs from the parent Requirement's
- **THEN** materialization fails naming the Requirement, expected and found values
- **AND** no Issue is created

#### Scenario: Missing or ambiguous routing input

- **WHEN** the parent has no `project:*` label or more than one, or required target configuration or the Backlog label is absent
- **THEN** materialization fails naming the missing or ambiguous input and creates nothing

#### Scenario: Read-back mismatch is not success

- **WHEN** the created or reused child lacks the expected `project:*` label, `type:internal-change` or the parent back-reference on read-back
- **THEN** materialization reports failure naming the child and no success result is produced

#### Scenario: Existing mislabeled child is a visible error

- **GIVEN** an exact-handoff child already exists with a contradictory or absent `project:*` label
- **WHEN** the handoff is retried
- **THEN** materialization fails with the child reference, expected and found labels and manual repair guidance
- **AND** no `project:*` label is added, removed or replaced

#### Scenario: Retry completes only the deterministic internal-change label

- **GIVEN** an exact-handoff child with the correct `project:*` label but missing `type:internal-change`
- **WHEN** the handoff is retried
- **THEN** the missing `type:internal-change` label is added once and re-verified before success
