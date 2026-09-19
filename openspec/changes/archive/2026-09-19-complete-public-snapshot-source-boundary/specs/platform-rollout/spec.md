## ADDED Requirements

### Requirement: Public rollout core contains no private-project compatibility branches

The public managed-rollout implementation SHALL express rollout and migration behavior in generic platform terms. Compatibility logic whose trigger, constants, hashes, messages, or code payloads are specific to a private downstream repository SHALL NOT be hard-coded into the public core.

#### Scenario: Existing operator still needs a project compatibility override
- **WHEN** an existing private managed project still requires a compatibility transformation during rollout
- **THEN** the compatibility material is supplied through an explicitly operator-owned external mechanism or handled through a reviewed one-time downstream migration
- **AND** the public core sees only the generic extension/migration contract
- **AND** the private project's name, production-specific hashes, and override source do not enter the public snapshot.

#### Scenario: Compatibility can be removed
- **WHEN** a project-specific shim is no longer required after a controlled downstream migration
- **THEN** the public implementation removes that shim rather than preserving it indefinitely as product behavior
- **AND** regression tests use synthetic fixtures for any generic invariant that still requires coverage.

### Requirement: Removing private compatibility does not silently break the operator fleet

Before deleting or externalizing an existing private-project compatibility path, the change SHALL identify whether any currently managed downstream project still depends on it and SHALL provide a bounded transitional action or explicit blocker.

#### Scenario: Private project still depends on legacy migration behavior
- **WHEN** repository evidence shows a current managed project needs one of the extracted compatibility transforms
- **THEN** the change records the required operator-owned compatibility configuration or downstream migration step
- **AND** public cutover does not claim operator rollout continuity until that transition is validated.

#### Scenario: No current dependency remains
- **WHEN** repository/operator evidence shows the legacy project-specific transform is no longer needed
- **THEN** the shim is deleted from public code
- **AND** no replacement private payload is created merely for historical preservation.
