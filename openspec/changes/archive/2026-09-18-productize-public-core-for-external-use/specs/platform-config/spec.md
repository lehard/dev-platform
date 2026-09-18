## ADDED Requirements

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
