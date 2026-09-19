## ADDED Requirements

### Requirement: Public Project Factory evidence uses synthetic operator identities

Project Factory tests, examples, and accepted specifications SHALL distinguish optional operator participation from the maintainer's own operator installation. Generic evidence SHALL use synthetic repository/project identities and SHALL NOT require the maintainer's concrete Development Backlog repository.

#### Scenario: Operator-enabled render is tested
- **WHEN** tests exercise a rendered project with Development Backlog participation
- **THEN** the test provides a synthetic backlog repository and Project identity through the supported operator configuration path
- **AND** assertions verify behavior rather than the maintainer's repository name.

#### Scenario: No-operator render is tested
- **WHEN** tests exercise a generic render without operator participation
- **THEN** no concrete maintainer backlog/fleet identity appears in the output
- **AND** the existing portable lifecycle remains fully verified.

## MODIFIED Requirements

### Requirement: Project Factory renders a generic project without operator coupling by default

Project Factory SHALL be able to render a usable Dev Platform project without embedding the source operator's repository inventory, backlog repository, GitHub Project owner/number, bot identity, promotion repository, or process-health installation settings. Operator-specific integrations SHALL be explicit opt-ins and SHALL NOT be required for OpenSpec, task isolation, checks, or the standard project lifecycle.

#### Scenario: External user renders a default standard project
- **WHEN** a user renders a new standard project without enabling operator integrations
- **THEN** the generated repository contains the portable Dev Platform contract, OpenSpec integration, task lifecycle and verification surfaces
- **AND** it does not contain the source operator's concrete project inventory, concrete Development Backlog repository, GitHub Project #1, owner-specific bot login, or equivalent source-installation defaults
- **AND** the project can run its local readiness/verification path without access to the source operator's fleet infrastructure.

#### Scenario: Operator integration is enabled explicitly
- **WHEN** an operator deliberately enables a backlog, fleet or process-management capability and supplies its own configuration
- **THEN** Project Factory renders only the selected integration surfaces
- **AND** the resulting values come from that operator's explicit configuration rather than hard-coded source-repository defaults.
