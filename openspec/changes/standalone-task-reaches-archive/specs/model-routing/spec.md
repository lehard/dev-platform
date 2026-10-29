## ADDED Requirements

### Requirement: A task in the main copy of a project can record its retained outcome after implementation

For a supervisor-retained route in the `standalone-clone` topology with no delegated child, the containment postcheck SHALL accept implementation commits made after route preparation, so the retained outcome can be recorded, the change archived and published. It SHALL accept a HEAD move only when the current HEAD is a descendant of the snapshot HEAD, and SHALL still report a violation for a non-descendant HEAD, for any new, changed or vanished path in the working tree other than platform lifecycle records, and for any change to a path that was already dirty at the snapshot. Routes in the linked-worktree topology SHALL keep the existing postcheck. Shipped hints, errors and docs SHALL name only commands that exist in a rendered project, and the managed task state file SHALL NOT be committed to a project's repository.

#### Scenario: Implementation commits in the main copy
- **GIVEN** a standalone-clone route prepared at HEAD H with a retained plan
- **WHEN** the supervisor commits the implementation and records the retained outcome
- **THEN** the outcome is recorded with the commits as `task_commits`
- **AND** the change can be archived and published

#### Scenario: Leftover or foreign change in the main copy
- **WHEN** the working tree has an uncommitted or untracked path, a changed pre-existing dirty path, or HEAD moved to a commit that is not a descendant of the snapshot HEAD
- **THEN** recording the retained outcome fails with a containment violation naming it

#### Scenario: Rendered project hints
- **WHEN** a routing gate or error suggests a recovery command
- **THEN** every command it names exists in the rendered project

#### Scenario: Task state is not committed
- **WHEN** a managed task writes `.managed-task-state.json` in a project that does not ignore it
- **THEN** the file is ignored locally by the repository's exclude file and does not appear as untracked
