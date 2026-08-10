## ADDED Requirements

### Requirement: Project-owned harness workflow guidance is preserved during upgrades

For `harness_mode=project`, Copier SHALL preserve an existing repository-owned `docs/engineering/agent-workflow.md` rather than replacing it with the generic platform harness guide.

#### Scenario: Mature project owns workflow guidance

- **GIVEN** `harness_mode=project`
- **AND** `docs/engineering/agent-workflow.md` already exists
- **WHEN** a reviewed Copier upgrade is applied
- **THEN** that file is preserved without conflict
- **AND** repository-specific publication and CI guidance remains authoritative

#### Scenario: Platform owns workflow guidance

- **GIVEN** `harness_mode=platform`
- **WHEN** a Copier upgrade changes generic workflow guidance
- **THEN** the platform-managed `docs/engineering/agent-workflow.md` remains eligible for update