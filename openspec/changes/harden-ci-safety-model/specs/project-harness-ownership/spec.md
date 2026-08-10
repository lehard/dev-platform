# Project Harness Ownership

## ADDED Requirements

### Requirement: Project-owned workflow guidance is preserved during managed rollout
For `harness_mode=project`, repository-specific `docs/engineering/agent-workflow.md` SHALL be preserved by Copier updates rather than treated as a platform-owned generated file.

#### Scenario: Mature project customized its agent workflow documentation
- **GIVEN** a managed repository uses `harness_mode=project`
- **AND** it has repository-specific `docs/engineering/agent-workflow.md`
- **WHEN** a new Dev Platform release is rolled out
- **THEN** Copier leaves that file unchanged
- **AND** the rollout can update platform-owned files without producing a conflict solely because of that project-specific workflow document
