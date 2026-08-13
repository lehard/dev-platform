## ADDED Requirements

### Requirement: Managed projects can adopt the bounded process-health loop

After central acceptance, the platform-managed project template SHALL expose the supported process-health review capability and required bounded configuration/labels without requiring a repository-specific fork of the workflow. Project-scoped friction SHALL remain in the project repository while platform-scoped friction SHALL continue to route to the configured central platform repository.

#### Scenario: Managed downstream project adopts the current platform

- **GIVEN** a supported managed project adopts a platform version containing the accepted process-health capability
- **WHEN** the project records and reviews process friction
- **THEN** project-level evidence is reviewed in that repository under the shared contract
- **AND** platform-level evidence continues to route to the configured central platform repository
- **AND** the project does not need a separate bespoke problem-management implementation

#### Scenario: Dashboard is absent

- **WHEN** no cross-repository GitHub Project dashboard is configured
- **THEN** GitHub issues, managed-task linkage and dated review reports remain complete sources of truth
- **AND** process-health lifecycle behavior remains fully operable
