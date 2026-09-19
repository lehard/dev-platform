# Platform Configuration Specification

## Purpose

Platform configuration SHALL preserve reviewed downstream project settings while allowing explicit platform migrations to maintain required platform-owned metadata.
## Requirements
### Requirement: Downstream platform configuration is preserved across rollout

`.dev-platform.toml` SHALL be created for a fresh project and SHALL be treated as project-owned configuration after creation. Copier update SHALL preserve reviewed downstream values while platform bootstrap may mechanically migrate platform-owned fields.

#### Scenario: Project stores extra platform configuration

- **GIVEN** an adopted project has a reviewed `project_required_files` value in `.dev-platform.toml`
- **WHEN** Copier updates to a newer platform release
- **THEN** that project-specific value survives without a `.rej` conflict

#### Scenario: Stable platform release advances

- **GIVEN** `.dev-platform.toml` is preserved during Copier update
- **WHEN** `_commit` advances to `vX.Y.Z`
- **THEN** bootstrap updates only the required platform-owned version field so `platform_version` becomes `X.Y.Z`

### Requirement: Portable project configuration is separate from operator installation state

Committed project configuration SHALL describe the repository's portable engineering contract. Operator-wide fleet inventory, private backlog bindings, account-specific bot identities and cross-repository rollout policy SHALL live outside the generic project contract unless a project explicitly opts into an integration that requires a portable reference.

#### Scenario: Project has no operator configuration
- **WHEN** a generated project is used independently of the source operator
- **THEN** local lifecycle, OpenSpec and verification commands resolve entirely from portable project/repository configuration
- **AND** absence of external operator configuration is not an error for ordinary project work.

#### Scenario: External operator configuration is supplied
- **WHEN** an operator supplies a supported external operator configuration source
- **THEN** operator-only fleet/backlog/rollout behavior reads from that source
- **AND** project-portable configuration remains usable when the external operator layer is absent.

### Requirement: Generic distribution does not carry a concrete managed-project inventory

The public Dev Platform distribution SHALL NOT ship a live inventory of one operator's managed, candidate or excluded repositories as generic product state. If fleet management remains a public capability, its implementation SHALL accept an external registry or an explicitly created operator-owned registry.

#### Scenario: Public release candidate is rendered or packaged
- **WHEN** the public source/release candidate is validated
- **THEN** no concrete personal project registry is required or emitted as canonical generic state
- **AND** fleet-management code, if present, is testable with fixtures/example data rather than the owner's live project list.

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

### Requirement: Development Backlog identity remains operator-owned

Concrete Development Backlog repository, GitHub Project owner/number, labels, and related installation identity SHALL remain external operator configuration rather than canonical Dev Platform source identity.

#### Scenario: Generic public source is installed without operator configuration
- **WHEN** a user clones or renders Dev Platform without an operator layer
- **THEN** no concrete Development Backlog repository owned by the Dev Platform maintainer is required by runtime, tests, accepted specs, or examples
- **AND** portable OpenSpec/task/verification behavior remains usable.

#### Scenario: Current maintainer runs managed authoring
- **WHEN** the maintainer explicitly enables the operator layer and supplies the external operator TOML
- **THEN** managed authoring resolves the real backlog and Project from that TOML
- **AND** the real values stay outside public source.

### Requirement: Operator handoff is explicit before fleet rollout

The public source SHALL document the external fields required for the current operator to resume managed fleet rollout after private compatibility data has been removed from source. Documentation SHALL name configuration keys and validation commands, but SHALL NOT commit the operator's real repository inventory, real legacy fingerprints, tokens, or credentials.

#### Scenario: Operator prepares for next real rollout
- **WHEN** public cutover preparation is complete
- **THEN** the handoff checklist identifies at least the external Development Backlog configuration, `rollout.registry_path`, rollout bot identity as applicable, and any required `rollout.legacy_harness_migrations` values
- **AND** it identifies a validation/doctor command to prove the external configuration before fleet mutation
- **AND** absence of required real continuity data causes rollout to fail closed rather than fall back to hidden public defaults.

