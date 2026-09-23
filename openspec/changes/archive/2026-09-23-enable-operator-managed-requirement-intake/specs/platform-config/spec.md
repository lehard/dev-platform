# platform-config Specification Delta

## ADDED Requirements

### Requirement: Generic operator integration can be explicitly selected without installation identity

The Project Factory SHALL offer a default-off `operator_integration` selection for an operator-managed downstream project. When selected, its committed portable reference SHALL enable the operator layer through the existing `DEV_PLATFORM_OPERATOR_CONFIG` environment-name contract; it SHALL NOT contain an operator TOML path, owner, Backlog repository, credential, or managed-project identity.

#### Scenario: Fresh project remains portable

- **WHEN** a project is rendered with `operator_integration` false or omitted
- **THEN** its configuration contains no operator opt-in
- **AND** a process-global operator environment value remains ignored

#### Scenario: Operator-managed project is rendered

- **WHEN** a project is rendered with `operator_integration` true
- **THEN** its configuration explicitly enables the operator layer and names `DEV_PLATFORM_OPERATOR_CONFIG`
- **AND** runtime resolves operator-owned state through the existing external resolver

#### Scenario: Existing explicit path configuration is upgraded

- **GIVEN** a project already uses a reviewed explicit `operator_config_path` or enabled operator table
- **WHEN** it updates to a release with the generic selection
- **THEN** its existing operator configuration remains valid and is not silently replaced

#### Scenario: Existing operator table conflicts with requested migration

- **GIVEN** a selected managed project has a disabled or incomplete existing `[operator]` table
- **WHEN** rollout attempts to activate generic integration
- **THEN** rollout fails before publication with a precise conflict diagnostic
