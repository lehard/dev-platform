## ADDED Requirements

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
