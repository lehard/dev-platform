## ADDED Requirements

### Requirement: Concrete multi-agent scope claims are admission-controlled atomically

For a platform-owned `multi-agent` workflow, the lifecycle SHALL use the canonical task identity and normalized repository-relative scope information from the existing worktree-coordination mechanism to make a race-safe admission decision before the task performs its first implementation change. Admission and recording of a concrete-path claim SHALL be atomic relative to the machine-local coordination state.

The admission result SHALL be:

- `RUN` when no conflicting hard overlap is present and the current task has atomically acquired its concrete claims; or
- `WAIT` when a conflicting active task already owns a hard-overlapping concrete path.

#### Scenario: Two tasks race to claim the same concrete file

- **GIVEN** tasks A and B concurrently attempt to claim the same currently free repository-relative file path
- **WHEN** both admission operations execute
- **THEN** at most one task receives `RUN` for that path
- **AND** the other task receives `WAIT`
- **AND** both tasks cannot begin implementation under simultaneous ownership of the same concrete path

#### Scenario: Independent concrete claims are admitted

- **GIVEN** active task scopes contain no hard-overlapping concrete file with the current task
- **WHEN** admission runs
- **THEN** the current task may receive `RUN`
- **AND** unrelated tasks remain able to execute concurrently

### Requirement: Hard and soft overlap are classified deterministically

The coordination mechanism SHALL distinguish a hard overlap from a soft or potential overlap using normalized repository-relative scope evidence. An exact concrete file path present in the current task's claim and another active task's concrete claimed or factual scope SHALL be a hard overlap. A shared directory, subsystem, broad glob, or other non-concrete proximity SHALL remain advisory by itself.

When an active task has factual changed-file scope, that concrete evidence SHALL take precedence over a broader declared scope for determining hard overlap; the broader declaration MAY still contribute a warning.

#### Scenario: Active task already changes the same file

- **GIVEN** active task A factually changes `template/scripts/_platform_common.py`
- **AND** task B claims that same concrete file
- **WHEN** task B runs admission
- **THEN** task B receives `WAIT`
- **AND** the diagnostic identifies task A and the conflicting repository-relative path

#### Scenario: Only a broad subsystem overlaps

- **GIVEN** task A and task B both mention the same directory, subsystem, or broad glob
- **AND** no exact concrete file conflict is established
- **WHEN** admission runs
- **THEN** the overlap is reported as soft or potential
- **AND** that overlap alone does not force `WAIT`

#### Scenario: Factual scope disproves a broad declared conflict

- **GIVEN** an active task declared a broad scope
- **AND** its available factual changed-file scope contains no concrete path claimed by the current task
- **WHEN** admission classifies the overlap
- **THEN** the broad declaration does not become a hard blocker by itself

### Requirement: Admission diagnostics are bounded and privacy-preserving

A hard-overlap diagnostic SHALL identify the current managed or quick task, the conflicting active task, and a bounded set of conflicting repository-relative paths. It SHALL follow the existing coordination privacy contract and SHALL NOT expose unnecessary absolute local paths, secrets, or unrelated task state.

#### Scenario: Hard overlap is reported

- **WHEN** admission returns `WAIT`
- **THEN** the result contains enough bounded task/path context to explain the conflict and support a later retry
- **AND** unrelated local machine details are omitted
