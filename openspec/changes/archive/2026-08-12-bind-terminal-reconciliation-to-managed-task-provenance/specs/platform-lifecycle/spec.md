## ADDED Requirements

### Requirement: Managed terminal side effects use exact task provenance

For a Development Backlog managed task, platform-owned terminal reconciliation SHALL perform Project-status and related managed side effects only for the source identity bound to the exact delivered task. Shared integration state SHALL NOT be the sole or higher-precedence source of managed task identity after execution has moved out of the task checkout.

#### Scenario: Exact task PR merges while integration state belongs to another task

- **GIVEN** GitHub confirms the exact-head PR for task A as `MERGED`
- **AND** integration-visible managed state identifies task B
- **WHEN** terminal reconciliation begins
- **THEN** the GitHub merge for task A remains authoritative
- **AND** the lifecycle does not update task B
- **AND** managed Project mutation is blocked until task A's identity can be safely reconciled

#### Scenario: Correct task identity reaches terminal completion

- **GIVEN** task A's exact managed identity is preserved through publication
- **WHEN** remote merge and local reconciliation complete
- **THEN** only source Issue A is reconciled to the appropriate terminal Project state
- **AND** repeating terminal reconciliation is idempotent

#### Scenario: Status reconciliation fails after confirmed merge

- **WHEN** the exact task PR is already `MERGED`
- **AND** managed Project reconciliation cannot safely complete
- **THEN** the task remains remotely merged
- **AND** the lifecycle records or reports a resumable pending-reconciliation state tied to that exact task
- **AND** a later retry continues without creating a second delivery path
