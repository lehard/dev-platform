## MODIFIED Requirements

### Requirement: Concrete multi-agent scope claims are admission-controlled atomically

For a platform-owned `multi-agent` workflow, the lifecycle SHALL use the canonical task identity and normalized repository-relative scope information from the existing worktree-coordination mechanism to make a race-safe admission decision before the task performs its first implementation change. Admission and recording of a concrete-path claim SHALL be atomic relative to the machine-local coordination state.

Only a valid active board entry with a proven canonical worktree/branch identity may contribute a blocking concrete-file claim. A degraded or terminal sibling entry MAY produce a bounded hygiene diagnostic, but SHALL NOT by itself make an otherwise independent task wait or fail to start. An unreadable or un-lockable coordination store remains an admission error and SHALL fail closed.

The admission result SHALL be:

- `RUN` when no conflicting valid active concrete-file claim is present and the current task has atomically acquired its concrete claims; or
- `WAIT` when a valid active task already owns a hard-overlapping concrete path.

#### Scenario: Two tasks race to claim the same concrete file

- **GIVEN** tasks A and B concurrently attempt to claim the same currently free repository-relative file path
- **WHEN** both admission operations execute
- **THEN** at most one task receives `RUN` for that path
- **AND** the other task receives `WAIT`
- **AND** both tasks cannot begin implementation under simultaneous ownership of the same concrete path

#### Scenario: Independent concrete claims are admitted

- **GIVEN** valid active task scopes contain no hard-overlapping concrete file with the current task
- **WHEN** admission runs
- **THEN** the current task may receive `RUN`
- **AND** unrelated tasks remain able to execute concurrently

#### Scenario: A sibling board record has a branch/path mismatch

- **GIVEN** a sibling board entry names a registered worktree whose checked-out branch does not equal its declared branch
- **AND** the current task has no hard overlap with any valid active claim
- **WHEN** the current task starts and requests admission
- **THEN** the mismatch is reported as bounded hygiene information
- **AND** the independent task may receive `RUN` and materialize in its own worktree
- **AND** the lifecycle does not modify the sibling worktree, branch or board entry merely to proceed

#### Scenario: A valid sibling owns the same concrete file

- **GIVEN** a valid active sibling entry owns a concrete repository-relative file also claimed by the current task
- **WHEN** the current task requests admission
- **THEN** the current task receives `WAIT`
- **AND** the diagnostic identifies the sibling task and bounded conflicting path

#### Scenario: Board state cannot be read or locked

- **WHEN** the lifecycle cannot read or acquire the machine-local coordination state safely
- **THEN** admission fails before starting implementation
- **AND** it does not infer that sibling claims are absent
