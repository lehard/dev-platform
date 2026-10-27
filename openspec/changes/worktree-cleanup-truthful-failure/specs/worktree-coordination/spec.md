## ADDED Requirements

### Requirement: Worktree cleanup reports failures truthfully

`worktree_cleanup.py cleanup` SHALL NOT report success for a cleanup that recorded an error or was refused. A targeted cleanup that recorded an error SHALL have status `failed`; a global cleanup that recorded an error SHALL keep status `completed-with-errors`. The command SHALL exit non-zero whenever the cleanup result carries an error or has status `refused` or `failed`, for a targeted and for a global cleanup, and SHALL exit zero only for a successful, already-cleaned or previewed cleanup without errors.

#### Scenario: Targeted cleanup fails

- **WHEN** a targeted cleanup cannot remove its deferred worktree and records the error
- **THEN** the result has status `failed` with the error and the command exits non-zero

#### Scenario: Global cleanup with an error

- **WHEN** `cleanup --all --apply` removes some worktrees and records an error for another
- **THEN** the result has status `completed-with-errors` and the command exits non-zero

#### Scenario: Refused global preview

- **WHEN** `cleanup --all` is refused
- **THEN** the command exits non-zero

#### Scenario: Clean cleanup

- **WHEN** a targeted cleanup removes its worktree, or finds it already cleaned, without errors
- **THEN** the command exits zero
