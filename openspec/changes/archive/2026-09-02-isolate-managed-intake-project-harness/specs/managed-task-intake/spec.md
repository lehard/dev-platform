## ADDED Requirements

### Requirement: Managed start is independent of project-owned publication APIs

The standard managed-task start entrypoint SHALL remain dependency-light for a
repository whose configuration declares `harness_mode=project`. Before a
project task is admitted, its import and preflight path SHALL NOT require a
symbol, class, or callable supplied only by a project-owned publication file.
Shared platform lifecycle types and operations SHALL be owned by a
platform-managed module or gated to a proven platform-harness-only operation.

#### Scenario: Jara-shaped project harness lacks a platform publication type

- **GIVEN** a valid managed package targets a repository with
  `harness_mode=project`
- **AND** its preserved `scripts/project_publish.py` does not expose the
  platform harness `PrRef` type
- **WHEN** the standard managed-start entrypoint validates and starts the task
- **THEN** it completes the normal managed admission and materialization path
  without importing that project-owned publication API
- **AND** the resulting worktree, provenance, and source-issue status flow use
  the ordinary managed lifecycle rather than a project-specific workaround

#### Scenario: Platform-only publication dependency is unavailable

- **GIVEN** a platform-harness-only pending-rollout operation requires a
  platform-owned publication dependency that cannot be loaded
- **WHEN** managed start reaches that proven platform-only operation
- **THEN** it fails closed with an actionable dependency diagnostic
- **AND** it does not create task worktree, board, or source Issue/Project
  status side effects before the failed admission

### Requirement: Project-harness compatibility coverage exercises the standard entrypoint

The platform SHALL maintain regression coverage for representative
project-owned harnesses at the actual standard managed-start entrypoint, not
only for isolated helpers or a project-specific recovery command.

#### Scenario: Project-owned publication surface evolves independently

- **GIVEN** a compatibility fixture preserves a project-owned publication
  module whose exports differ from the platform harness
- **WHEN** platform validation exercises managed start for that fixture
- **THEN** the fixture proves the standard entrypoint neither imports nor
  assumes the differing project-owned API
- **AND** platform-harness exact-head pending-rollout coverage remains green
