## ADDED Requirements

### Requirement: Managed Project status follows actual execution lifecycle

For a task with an unambiguous managed Development Backlog source, the
platform-owned lifecycle SHALL keep the configured GitHub Project `Status`
consistent with actual execution/delivery state. The Project field SHALL be a
human-facing projection of lifecycle evidence rather than an independent task
state machine.

#### Scenario: Managed task is successfully claimed

- **GIVEN** the source managed task is authorized as `Ready`
- **WHEN** the standard managed start path successfully validates the source and establishes its task workspace
- **THEN** the Project item is reconciled to `In progress` before implementation continues
- **AND** a Project mutation/configuration failure is surfaced rather than silently leaving active work in `Ready`

#### Scenario: Import is performed without task claim

- **WHEN** a supported managed OpenSpec package is only discovered/imported outside a successful managed execution claim
- **THEN** that package operation alone does not change Project workflow status

### Requirement: Managed delivery projects review and terminal states truthfully

The platform SHALL project reviewable delivery as `In review`, genuine external
stops as `Blocked`, and terminal reconciled completion as `Done`. Transient CI
waiting SHALL NOT be misclassified as a blocker.

#### Scenario: Exact task PR is published

- **GIVEN** a managed task is active
- **WHEN** its exact reviewable delivery PR is created or safely reused
- **THEN** the Project item is reconciled to `In review`
- **AND** it remains non-terminal while checks/review/merge are pending

#### Scenario: Lifecycle requires external action

- **WHEN** the managed lifecycle reaches a supported blocker that cannot continue without a human/external action or decision
- **THEN** the Project item is reconciled to `Blocked`
- **AND** the blocker is surfaced with actionable context

#### Scenario: Blocked task resumes

- **WHEN** the external blocker is resolved and lifecycle resumes
- **THEN** reconciliation restores `In progress` or `In review` according to the current execution/delivery evidence

#### Scenario: Required checks are merely pending

- **WHEN** an active managed PR is waiting for normal required checks or accepted automatic merge processing
- **THEN** its status remains `In review`
- **AND** the lifecycle does not use `Blocked` solely because remote processing is incomplete

#### Scenario: Managed delivery completes

- **GIVEN** GitHub confirms the exact managed delivery is merged
- **WHEN** required local/source-task reconciliation reaches terminal success
- **THEN** the configured Project item is reconciled to `Done`
- **AND** open/green-but-unmerged delivery cannot produce `Done`

### Requirement: Managed Project status reconciliation is idempotent and recoverable

Status synchronization SHALL be safe to retry and SHALL use unambiguous source
Issue/Project identity plus authoritative lifecycle evidence. It SHALL support
repairing stale status after interruption without creating duplicate Project
items or redefining Git/PR truth.

#### Scenario: Desired status is already current

- **WHEN** reconciliation observes that the Project item already has the desired lifecycle status
- **THEN** it performs no workflow-changing mutation
- **AND** returns success

#### Scenario: Remote merge succeeded but Project update failed

- **GIVEN** GitHub already confirms the exact task PR as merged
- **WHEN** Project mutation is unavailable or fails
- **THEN** the merge remains authoritative
- **AND** lifecycle reports Project reconciliation as pending/blocking full workflow completion
- **AND** a later retry can set the correct Project state without creating another delivery

#### Scenario: Historical item is stale

- **GIVEN** an existing managed item still shows `Ready` or another stale value
- **AND** its source and lifecycle/delivery evidence unambiguously imply another supported state
- **WHEN** explicit recovery reconciliation is run
- **THEN** the Project item is repaired to that supported state
- **AND** ambiguity causes no mutation and is reported for human resolution

### Requirement: Human readiness authorization remains human-owned

Automatic status synchronization SHALL NOT select work from the backlog or grant
execution authorization.

#### Scenario: Managed task is still in Backlog

- **WHEN** no human has moved/authorized the task as `Ready`
- **THEN** lifecycle status synchronization does not move it to `Ready` or start execution
- **AND** no dispatcher is implied by this capability
