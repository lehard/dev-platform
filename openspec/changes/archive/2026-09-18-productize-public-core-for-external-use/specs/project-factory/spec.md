## ADDED Requirements

### Requirement: Project Factory renders a generic project without operator coupling by default

Project Factory SHALL be able to render a usable Dev Platform project without embedding the source operator's repository inventory, backlog repository, GitHub Project owner/number, bot identity, promotion repository, or process-health installation settings. Operator-specific integrations SHALL be explicit opt-ins and SHALL NOT be required for OpenSpec, task isolation, checks, or the standard project lifecycle.

#### Scenario: External user renders a default standard project
- **WHEN** a user renders a new standard project without enabling operator integrations
- **THEN** the generated repository contains the portable Dev Platform contract, OpenSpec integration, task lifecycle and verification surfaces
- **AND** it does not contain concrete `lehard/*` project inventory, `lehard/development-backlog`, GitHub Project #1, owner-specific bot login or equivalent source-installation defaults
- **AND** the project can run its local readiness/verification path without access to the source operator's fleet infrastructure.

#### Scenario: Operator integration is enabled explicitly
- **WHEN** an operator deliberately enables a backlog, fleet or process-management capability and supplies its own configuration
- **THEN** Project Factory renders only the selected integration surfaces
- **AND** the resulting values come from that operator's explicit configuration rather than hard-coded source-repository defaults.

### Requirement: Project Factory selects SCM delivery independently from workflow complexity

Project Factory SHALL treat workflow profile and SCM/delivery provider as independent configuration axes. Selecting `standard` SHALL NOT imply GitHub, and selecting GitLab SHALL NOT require a forked template.

#### Scenario: Standard project selects GitLab
- **WHEN** a new standard project selects the GitLab delivery adapter
- **THEN** Project Factory renders the provider-neutral standard task lifecycle plus GitLab-specific delivery orchestration
- **AND** it does not render mandatory GitHub CLI/Actions publication dependencies.

#### Scenario: Existing GitHub project keeps GitHub behavior
- **WHEN** a standard project selects the GitHub delivery adapter
- **THEN** current supported PR/check publication semantics remain available
- **AND** provider-neutral changes do not weaken existing exact-head and required-check safety.
