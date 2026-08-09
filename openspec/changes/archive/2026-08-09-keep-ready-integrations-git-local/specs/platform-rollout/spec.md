## MODIFIED Requirements

### Requirement: Existing project-owned files survive platform rollout

The Project Factory SHALL create default project-owned control files for fresh repositories but SHALL preserve existing downstream content for files explicitly classified as project-owned during Copier updates.

#### Scenario: Existing managed project customized its project contract

- **GIVEN** a managed project already contains a customized `.gitignore`, `AGENTS.md`, `README.md`, `dev-platform/checks.toml`, or `openspec/config.yaml`
- **WHEN** Copier updates the project to a newer platform release
- **THEN** those existing files are preserved rather than patched or replaced by the platform template

#### Scenario: Platform needs clone-local generated-agent ignores

- **GIVEN** a mature repository owns its `.gitignore`
- **WHEN** local readiness regenerates machine-local Claude/Codex integrations
- **THEN** Dev Platform records its generated integration patterns in the clone-local Git exclude file rather than editing the project's tracked `.gitignore`
