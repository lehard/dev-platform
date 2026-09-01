# worktree-coordination Specification

## Purpose
TBD - created by archiving change harden-worktree-context-coordination. Update Purpose after archive.
## Requirements
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

### Requirement: Known same-file overlap can be acknowledged without falsifying scope

File-level hard overlap SHALL remain a default admission blocker. The platform MAY allow a task to proceed through an explicit bounded acknowledgment when an operator has verified that the concrete same-file overlap is intentionally safe. The acknowledgment SHALL record the current/conflicting task identities, exact conflicting repository-relative paths and a bounded reason, and SHALL NOT require the task to omit those paths from its truthful declared scope.

#### Scenario: Same file is intentionally shared

- **GIVEN** task A is active and claims file `x`
- **AND** task B also truthfully needs file `x`
- **WHEN** task B starts without an overlap acknowledgment
- **THEN** task B receives the normal hard-overlap `WAIT`
- **WHEN** an operator explicitly acknowledges the current A/B overlap on file `x` with a reason
- **THEN** task B may proceed without removing `x` from its declared scope
- **AND** the acknowledgment is retained as bounded coordination evidence

#### Scenario: Acknowledged overlap does not cover new files

- **GIVEN** an acknowledgment covers file `x`
- **WHEN** task B later overlaps task A on previously unacknowledged file `y`
- **THEN** the acknowledgment for `x` does not authorize `y`
- **AND** the new hard overlap requires a new coordination decision

### Requirement: Factual scope is rechecked before costly validation and publication

The platform SHALL compare the task's current factual changed-file scope with active task claims before costly protected validation and again at the publication boundary. A newly observed hard file overlap that is still active and not explicitly acknowledged SHALL block progression instead of remaining a warning-only diagnostic.

#### Scenario: Task scope expands after admission

- **GIVEN** tasks A and B were admitted without a hard overlap
- **WHEN** task B's factual diff later begins changing a concrete file actively claimed by task A
- **THEN** the pre-validation or pre-publication coordination gate stops task B before further costly/delivery work
- **AND** reports the active conflicting task and bounded repository-relative paths
- **AND** requires the overlap to clear or be explicitly acknowledged

#### Scenario: Conflicting task has completed

- **GIVEN** a previous hard overlap existed
- **WHEN** the sibling task is no longer active under the normal board lifecycle
- **THEN** its stale claim does not block the current task
- **AND** resume may proceed after the ordinary recheck

#### Scenario: Only soft scope overlap exists

- **WHEN** two active tasks share only a broad directory, subsystem or other non-file-specific scope
- **THEN** the platform emits a warning
- **AND** does not create a hard coordination blocker solely from that soft overlap

### Requirement: Scope claims use authoritative managed completion state when squash merge removes branch ancestry

Before a managed sibling claim blocks hard scope gating, the platform SHALL be able to reconcile that claim against the exact task's authoritative GitHub publication state. An exact merged PR SHALL be sufficient evidence that the sibling is completed for scope ownership even when squash merge means the feature branch is not an ancestor of `main`.

#### Scenario: Exact sibling PR was squash-merged

- **GIVEN** an active board claim belongs to an exact managed sibling task
- **AND** that task's exact PR is reported `MERGED` by GitHub
- **AND** the feature branch is not an ancestor of `main` because the repository used squash merge
- **WHEN** another task evaluates hard scope overlap
- **THEN** the completed sibling claim does not block the new task
- **AND** the decision does not require branch ancestry to reconstruct the squash merge

#### Scenario: Publication state is ambiguous or unavailable

- **WHEN** the platform cannot prove the exact sibling PR is merged
- **THEN** it retains the existing active claim
- **AND** hard overlap remains fail-closed

