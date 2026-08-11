## ADDED Requirements

### Requirement: Platform-owned check mappings do not silently collapse applicable coverage to zero commands

For `harness_mode=platform`, the rendered check-selection contract SHALL make the selected command set observable. When an affected scope is configured as requiring platform-managed checks, resolving that applicable scope to zero executable commands SHALL be treated as invalid check configuration rather than a successful validation result.

#### Scenario: Applicable configured scope resolves to no commands

- **GIVEN** a platform-owned harness and a changed scope matched by the project check configuration
- **WHEN** the matching check group contains no executable command
- **THEN** platform validation/doctor SHALL report a blocking configuration error
- **AND** SHALL NOT represent that group as passed

#### Scenario: Applicable configured scope resolves to commands

- **WHEN** the selected platform-owned check group resolves to one or more commands
- **THEN** the platform executes the selected commands according to the existing check policy
- **AND** reports the commands/results as executed evidence

#### Scenario: Project owns product verification

- **GIVEN** `harness_mode=project`
- **WHEN** Dev Platform validates common platform/OpenSpec health
- **THEN** it SHALL NOT require the repository-owned product harness to implement the platform selector contract
- **AND** SHALL NOT invent replacement product checks merely because platform-owned selection is absent

### Requirement: Platform-owned verification distinguishes syntax checks from product-test coverage

The platform SHALL report the type of configured check evidence truthfully and SHALL NOT imply that syntax/byte-compilation alone proves product-test coverage when the reviewed platform-owned check contract declares or detects a separate product test surface.

#### Scenario: Only compilation runs for a stack with configured test coverage

- **GIVEN** platform-owned configuration indicates an application/test surface beyond compilation
- **WHEN** verification executes only compile/syntax checks and no configured product test command
- **THEN** the platform SHALL report product-test coverage as unconfirmed
- **AND** SHALL fail closed when that missing command is an applicable required platform-managed check
