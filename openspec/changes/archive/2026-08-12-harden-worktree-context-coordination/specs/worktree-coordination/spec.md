## ADDED Requirements

### Requirement: Worktree registration has canonical identity

Multi-agent board registration SHALL accept a canonical absolute path for the declared branch and SHALL reject a relative, nested, missing, main-copy or branch-mismatched path with an actionable domain error before it writes shared board state or launches a subprocess.

#### Scenario: Ambiguous relative path is supplied

- **WHEN** a caller supplies a relative worktree path whose resolution is not explicitly defined by the board contract
- **THEN** registration fails with an error explaining that an absolute registered worktree path is required
- **AND** no board entry or worktree mutation is created

#### Scenario: Path and branch do not match

- **WHEN** a path resolves to a worktree whose checked-out branch differs from the declared branch, or resolves to integration main
- **THEN** registration rejects the request before writing state

### Requirement: Lifecycle exposes materially overlapping active scope

The multi-agent lifecycle SHALL compare a task's declared and factual changed-file scope against valid active board entries at registration and before publication. A material overlap SHALL produce a bounded actionable diagnostic before costly validation or remote mutation, without automatically modifying either task.

#### Scenario: Active tasks overlap one file

- **GIVEN** another valid active entry claims or changes a file also claimed or changed by the current task
- **WHEN** the current task registers or reaches publication preflight
- **THEN** the lifecycle identifies the overlapping path and task identity
- **AND** it asks the operator to coordinate or serialize the work
- **AND** it performs no automatic rebase, merge, reset, stash or cleanup

#### Scenario: Active tasks are independent

- **GIVEN** active task scopes do not overlap
- **WHEN** registration or publication preflight runs
- **THEN** no overlap diagnostic blocks the normal lifecycle
