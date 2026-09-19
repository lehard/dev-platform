## ADDED Requirements

### Requirement: External operator state requires explicit project opt-in

A portable project SHALL ignore operator configuration environment variables unless the project configuration explicitly enables the operator layer. Presence of a process-global `DEV_PLATFORM_OPERATOR_CONFIG` value by itself SHALL NOT change the effective configuration of a project that has no operator opt-in.

#### Scenario: Global operator env exists but project is portable
- **GIVEN** `DEV_PLATFORM_OPERATOR_CONFIG` is set in the parent environment
- **AND** the project has no explicit operator configuration/enablement
- **WHEN** project configuration is loaded
- **THEN** no external operator tables are merged
- **AND** Development Backlog, rollout, process-health, or fleet behavior is not activated.

#### Scenario: Project explicitly opts in to operator layer
- **GIVEN** the project records the supported explicit operator opt-in
- **WHEN** the configured operator source is available
- **THEN** operator-only commands may load the external operator state
- **AND** ordinary portable project behavior continues to work when operator-only commands are not invoked.

### Requirement: Operator configuration owns registry discovery coherently

The supported operator contract SHALL expose one coherent configuration path for backlog/fleet/rollout state. The managed-project registry location SHALL be resolvable from the operator configuration, with any CLI override having explicit documented precedence. A separate undocumented environment path SHALL NOT be required to make the example configuration work.

#### Scenario: Operator example is used as documented
- **WHEN** an operator creates an external configuration from the public example and points the project/operator opt-in to it
- **THEN** backlog metadata and rollout registry location are discoverable by the corresponding operator commands
- **AND** the example keys match keys actually consumed by runtime code.

#### Scenario: Registry is missing or invalid
- **WHEN** an operator-only fleet/rollout action needs the registry and its configured path is missing or invalid
- **THEN** the action fails explicitly with the resolved source/path reason
- **AND** ordinary non-operator project work is unaffected.

### Requirement: Operator-owned configuration can be validated without entering public source

The platform SHALL provide a bounded validation/doctor path for external operator configuration and registry state. Validation SHALL not copy the live operator inventory or credentials into the public repository.

#### Scenario: Owner validates personal operator installation
- **WHEN** the owner supplies the external operator config through the explicit opt-in path
- **THEN** the validator checks the supported tables, registry path/schema, and required operator fields
- **AND** emits secret-safe diagnostics
- **AND** no live inventory is staged or committed into the public source tree.
