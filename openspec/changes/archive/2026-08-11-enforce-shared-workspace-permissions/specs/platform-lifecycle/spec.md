## ADDED Requirements

### Requirement: Lifecycle preflights shared workspace access before mutation

The platform lifecycle SHALL validate and, where authorized, idempotently repair
the group collaboration contract for the platform-owned paths needed by the
next operation. The check SHALL include the integration root, registered task
worktree administration, required Git common-directory metadata and
platform-owned machine-local state. An unrepairable permission blocker SHALL be
surfaced before the next remote mutation whenever authoritative remote state has
not already changed.

#### Scenario: Restrictive drift is safely repairable

- **GIVEN** a platform-owned shared file is missing group write or a shared
  directory is missing group write/setgid
- **AND** the current user is authorized to change that bounded path
- **WHEN** lifecycle preflight runs
- **THEN** it restores the reviewed shared-group contract idempotently
- **AND** proceeds without requiring an alternate Git object store

#### Scenario: Restrictive drift is owned by another user

- **GIVEN** a required path cannot be repaired by the current process
- **WHEN** a managed lifecycle operation reaches preflight
- **THEN** it stops before the next remote mutation
- **AND** reports the exact path and minimal owner action required
- **AND** it does not stash, reset, clean, sudo or widen access beyond the
  reviewed group

#### Scenario: Remote merge is already authoritative

- **GIVEN** the exact managed PR is already GitHub-confirmed merged
- **AND** local reconciliation is blocked by restrictive shared permissions
- **WHEN** finish is retried after the owner repairs those paths
- **THEN** it resumes local-main, source-state, board and cleanup reconciliation
  without republishing or changing the merged result

### Requirement: File-producing lifecycle operations preserve group access

Platform-owned entry points SHALL set a cooperative creation mask where POSIX
semantics apply and SHALL explicitly set the final shared mode for secure
temporary files before atomic publication. They SHALL validate the affected
shared paths after file-producing operations that may ignore the creation mask.

#### Scenario: Secure temporary API defaults to owner-only mode

- **WHEN** a platform writer creates an atomic temporary file with a secure
  owner-only default
- **THEN** it applies the reviewed group-readable/group-writable mode before
  replacing the shared destination
- **AND** the destination never regresses to owner-only mode

#### Scenario: Git recreates mutable metadata

- **WHEN** fetch, commit, worktree or reconciliation creates new Git metadata
- **THEN** shared-repository configuration and post-operation validation keep the
  required metadata writable by the reviewed group
- **AND** any remaining drift is reported with exact paths
