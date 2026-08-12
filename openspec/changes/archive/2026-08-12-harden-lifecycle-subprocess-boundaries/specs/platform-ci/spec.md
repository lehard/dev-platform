## ADDED Requirements

### Requirement: Platform validation subprocesses are isolated from parent repository overrides

Platform-owned validation/check commands SHALL NOT inherit parent Git environment overrides that bind the subprocess to a specific repository, worktree, index, common directory or object store unless that exact validation operation explicitly requires and scopes the override.

#### Scenario: Validation command creates an independent temporary repository

- **GIVEN** the parent lifecycle process contains repository-scoped Git environment overrides
- **WHEN** a selected platform validation command creates or operates on a temporary Git repository
- **THEN** the temporary repository uses its own worktree/index/object-store context
- **AND** its Git objects are not redirected into the parent repository solely because of inherited environment variables

#### Scenario: Validation command needs ordinary process environment

- **WHEN** a platform validation command runs under normal conditions
- **THEN** unrelated environment such as `PATH`, active tool/runtime environment and other required non-repository process context remains available
- **AND** isolation does not become a blanket environment reset

#### Scenario: One Git operation requires a scoped override

- **GIVEN** a specific platform-owned Git operation requires a repository-scoped environment override
- **WHEN** that operation completes
- **THEN** the override is limited to that operation
- **AND** subsequent validation subprocesses do not inherit it by default
