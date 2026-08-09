# Platform CI Specification

## Purpose

Platform CI SHALL validate platform-managed behavior without requiring downstream repositories to execute mutable or inaccessible logic from the central private repository.
## Requirements
### Requirement: Downstream CI has no private repository access prerequisite

Generated project CI SHALL execute platform-managed check scripts from the checked-out downstream repository and SHALL NOT require access to a private reusable workflow in `dev-platform`.

#### Scenario: Private project adopts the platform

- **WHEN** the project runs its generated CI without any cross-repository Actions Access setting
- **THEN** GitHub executes the platform-managed checks from local Copier-managed files

### Requirement: CI updates remain reviewed and versioned

The downstream CI workflow and check scripts SHALL remain Copier-managed project files so platform changes arrive through reviewed template updates rather than mutable remote execution.

#### Scenario: Platform changes generated CI behavior

- **WHEN** a newer platform version changes the generated CI contract
- **THEN** an existing project receives that change through a reviewable Copier update instead of automatically executing central branch content

### Requirement: Generated guidance matches self-contained CI behavior

Generated documentation SHALL state that downstream platform CI runs from Copier-managed local files and SHALL NOT instruct agents that CI executes a pinned private reusable workflow.

#### Scenario: Agent reads platform release guidance

- **WHEN** a downstream repository is generated or updated
- **THEN** its guidance describes reviewed Copier updates as the CI propagation mechanism and identifies `platform_ci_ref` only as legacy compatibility metadata

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
