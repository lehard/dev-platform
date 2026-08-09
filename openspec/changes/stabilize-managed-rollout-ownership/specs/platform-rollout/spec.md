# Platform rollout delta

## ADDED Requirements

### Requirement: Existing project-owned files survive platform rollout

The Project Factory SHALL create default project-owned control files for fresh repositories but SHALL preserve existing downstream content for files explicitly classified as project-owned during Copier updates.

#### Scenario: Existing managed project customized its project contract

- **GIVEN** a managed project already contains a customized `AGENTS.md`, `README.md`, `dev-platform/checks.toml`, or `openspec/config.yaml`
- **WHEN** Copier updates the project to a newer platform release
- **THEN** those existing files are preserved rather than patched or replaced by the platform template

### Requirement: Platform version metadata stays coherent

After Project Factory rendering or managed Copier update, `.dev-platform.toml` `platform_version` SHALL match the stable SemVer recorded by `.copier-answers.yml` `_commit` without the leading `v`.

#### Scenario: Managed rollout advances Copier version

- **WHEN** rollout updates `_commit` from `v1.0.2` to `v1.2.1`
- **THEN** `.dev-platform.toml` records `platform_version = "1.2.1"` before validation and commit

#### Scenario: Version metadata remains inconsistent

- **WHEN** rollout finishes Copier update but the two version records differ
- **THEN** rollout fails before pushing a branch or opening a PR

### Requirement: Project-specific doctor requirements are configuration data

Projects SHALL be able to declare additional required repository files in `.dev-platform.toml` without modifying the centrally managed `platform_doctor.py` implementation.

#### Scenario: Project requires a compatibility helper

- **GIVEN** `.dev-platform.toml` lists a project-specific required file
- **WHEN** `platform_doctor.py` runs
- **THEN** it verifies that file in addition to the shared platform requirements
