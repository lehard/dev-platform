## ADDED Requirements

### Requirement: Downstream platform CI respects harness ownership

Generated Dev Platform CI SHALL separate platform-owned hygiene from project-owned product verification according to `harness_mode`.

#### Scenario: Platform owns the project harness

- **GIVEN** `harness_mode=platform`
- **WHEN** generated Dev Platform CI runs
- **THEN** it MAY execute selected/full checks through the platform-managed selector contract in addition to platform/OpenSpec hygiene

#### Scenario: Project owns the project harness

- **GIVEN** `harness_mode=project`
- **WHEN** generated Dev Platform CI runs
- **THEN** it executes only dependency-independent platform/OpenSpec hygiene owned by Dev Platform
- **AND** it does not invoke product checks through the repository-owned selector
- **AND** it does not assume the repository-owned selector accepts platform-specific CLI flags

### Requirement: Existing project CI remains authoritative for product dependency setup

Adoption of a project-owned harness SHALL preserve the repository's existing CI as the authority for installing application dependencies and executing product-specific tests unless an explicit reviewed project change replaces that CI.

#### Scenario: Mature project already has dependency-aware CI

- **GIVEN** a repository CI creates its Python environment, installs backend dependencies, installs frontend dependencies and performs project-specific tests
- **WHEN** Dev Platform is adopted with `harness_mode=project`
- **THEN** generated platform CI does not duplicate those steps merely to satisfy platform adoption
- **AND** the existing CI remains available on the adoption PR

### Requirement: Platform hygiene remains enforced for project-owned harnesses

Choosing `harness_mode=project` SHALL NOT disable shared Dev Platform/OpenSpec health checks that do not require application dependency knowledge.

#### Scenario: Project-owned harness has stale completed OpenSpec change

- **GIVEN** a downstream project uses `harness_mode=project`
- **WHEN** platform lifecycle hygiene detects an active OpenSpec change whose tasks are all complete but which is not archived
- **THEN** generated platform CI fails according to the shared completion-lifecycle contract
