## ADDED Requirements

### Requirement: Deferred worktree cleanup is task-scoped by default

When terminal completion defers worktree housekeeping, the normal recovery path SHALL identify and clean only the exact deferred task/worktree record. A cleanup invocation that does not name a target SHALL NOT silently process all deferred records. Global cleanup MAY be supported only through an explicit `--all` mode with bounded candidate visibility before mutation.

#### Scenario: One task is cleaned while another remains deferred

- **GIVEN** two or more valid deferred worktree records exist
- **WHEN** cleanup is invoked for one exact task/worktree
- **THEN** only that record/worktree may be removed
- **AND** unrelated deferred worktrees remain unchanged.

#### Scenario: Global cleanup is requested

- **GIVEN** multiple deferred records exist
- **WHEN** the operator explicitly requests `--all`
- **THEN** the command exposes the eligible candidate set before mutation
- **AND** each candidate must independently pass the existing safety/identity checks
- **AND** ambiguous records fail closed rather than being guessed.
