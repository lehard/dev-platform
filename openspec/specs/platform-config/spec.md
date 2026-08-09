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
