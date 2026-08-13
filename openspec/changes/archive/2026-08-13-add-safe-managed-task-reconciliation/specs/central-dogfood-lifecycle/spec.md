## ADDED Requirements

### Requirement: Central reconciliation delegates to the shared lifecycle

The central source task adapter SHALL expose the supported managed-task reconciliation operation and delegate it to the shared lifecycle primitive. It SHALL not create a source-only branch, PR, publication journal, or alternative synchronization policy.

#### Scenario: Source task falls behind main

- **GIVEN** a central managed task status reports reconciliation required
- **WHEN** the operator invokes the central reconcile command
- **THEN** it delegates to the shared reconciliation lifecycle in the assigned task worktree
- **AND** subsequent validation and publication use the existing central finish path
