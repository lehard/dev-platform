# openspec-authoring Specification Delta

## MODIFIED Requirements

### Requirement: Active OpenSpec does not become a second backlog or manual lifecycle ledger

The platform SHALL bound the accepted current iteration through scope, non-goals, specs, and tasks. It SHALL NOT require Must/Should/Could classification, future-release roadmapping, manual OpenSpec status/date/expiry fields, or artifact inventories that duplicate authoritative lifecycle state.

#### Scenario: Future improvement is outside the accepted change

- **WHEN** authoring identifies a useful later enhancement outside the accepted result
- **THEN** it remains a non-goal or follow-up
- **AND** generic explicit fixation creates or reuses a Business Requirement without creating an OpenSpec package

#### Scenario: Lifecycle state changes

- **WHEN** a change moves through verification, archive, or publication
- **THEN** authoritative lifecycle state and receipts remain the source of truth
- **AND** no manually maintained proposal status field mirrors them
