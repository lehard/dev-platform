## ADDED Requirements

### Requirement: Generated-integration excludes are written to the common Git directory

The platform SHALL write generated-integration ignore rules to the exclude file Git reads for the repository (`git rev-parse --git-path info/exclude`), not under a linked worktree's private Git directory, so it never creates a per-worktree Git `info` directory outside the shared-workspace contract. A task worktree whose creation completed SHALL pass the shared-workspace audit for its Git administrative paths.

#### Scenario: Readiness run inside a linked task worktree

- **WHEN** the generated-integration excludes are ensured from a linked task worktree
- **THEN** the rules are present in the common `info/exclude`
- **AND** no `info` directory is created under that worktree's private Git directory

#### Scenario: Shared-workspace audit after start

- **WHEN** a task worktree has just been created and its readiness step has run
- **THEN** the shared-workspace audit reports no permission finding for that worktree's Git administrative paths
