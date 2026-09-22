# platform-rollout Specification Delta

## ADDED Requirements

### Requirement: Private managed rollout metadata can select generic operator integration

The private managed-project registry MAY record `operator_integration` as a boolean for each managed repository. The rollout matrix SHALL carry that boolean to the exact-version Copier update so the selected project's machine-owned Copier answer can activate the generic external-configuration reference. Public platform source SHALL NOT embed the selected repository identities or any operator installation configuration.

#### Scenario: Selected managed project is rolled out

- **GIVEN** a private registry entry is `managed` and sets `operator_integration` true
- **WHEN** exact-version rollout prepares its update branch
- **THEN** the candidate receives the generic operator-integration answer before rendering and bootstrap
- **AND** the resulting change remains a reviewable downstream pull request

#### Scenario: Registry entry omits the selection

- **WHEN** a managed registry entry does not set `operator_integration`
- **THEN** it is treated as false
- **AND** rollout does not add operator configuration to that project

#### Scenario: Registry selection is malformed

- **WHEN** `operator_integration` is present but not a boolean
- **THEN** registry validation fails before rollout planning
