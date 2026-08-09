# Platform Rollout Delta

## ADDED Requirements

### Requirement: Managed rollout isolates historical Copier tasks

Managed exact-version Copier update and guarded recopy SHALL skip embedded template tasks from historical source snapshots. After a conflict-free render, rollout SHALL execute the candidate version's platform bootstrap exactly once before project validation.

#### Scenario: Historical template has an obsolete bootstrap task

- **GIVEN** a managed project was created from an older platform release whose Copier task is incompatible with the available OpenSpec CLI
- **WHEN** managed rollout updates it to a newer exact platform version
- **THEN** historical Copier tasks are not executed
- **AND** the newly rendered candidate bootstrap synchronizes platform-owned metadata before validation

#### Scenario: Copier update has unresolved conflicts

- **WHEN** exact-version Copier update leaves an unresolved rejection or otherwise fails
- **THEN** rollout fails closed
- **AND** it does not execute the candidate bootstrap or push a downstream branch
