## ADDED Requirements

### Requirement: Generated repositories carry managed-task authoring configuration

The Project Factory SHALL render the configuration required for a participating repository to create managed tasks in the shared Development Backlog without embedding per-agent or machine-specific instructions. At minimum the rendered contract SHALL identify the backlog repository, project label and default priority.

#### Scenario: New managed repository is rendered

- **WHEN** a repository is generated/adopted with Development Backlog participation
- **THEN** its platform configuration contains the configured backlog repository, project label and default priority
- **AND** the repository's GitHub origin remains the authoritative target-repository identity used during authoring

#### Scenario: Existing managed repository receives authoring support

- **WHEN** the platform release containing managed-task authoring is applied through the normal Copier update path
- **THEN** the configuration/helper/guidance changes are presented as a reviewable update
- **AND** existing project-owned content is not silently overwritten to install the feature

### Requirement: Generated agent guidance exposes one cross-agent task protocol

The Project Factory SHALL render one canonical repository-wide task protocol in `AGENTS.md` covering discussion, managed-task fixation, managed-task import/execution and quick work. Tool-specific instruction files SHALL reference that protocol rather than fork its semantics.

#### Scenario: Repository supports Codex and Claude

- **WHEN** agent guidance is rendered for a repository with both tools available
- **THEN** `AGENTS.md` contains the authoritative managed/quick authoring and intake rules
- **AND** `CLAUDE.md` continues to import/reference `AGENTS.md`
- **AND** no duplicate Claude-specific managed-task rule set must be maintained

### Requirement: Authoring runtime is self-contained in generated repositories

The managed-task authoring entrypoint SHALL be delivered as part of the self-contained generated repository workflow and SHALL not require runtime access to the central `dev-platform` checkout.

#### Scenario: Agent authors a task in a downstream managed repository

- **WHEN** it invokes the standard managed-task authoring command
- **THEN** all platform-owned helper code needed for validation and GitHub publication is present in that repository
- **AND** the command uses configured GitHub/OpenSpec dependencies rather than importing mutable runtime code from `dev-platform@main`
