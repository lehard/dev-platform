## MODIFIED Requirements

### Requirement: The platform exposes abstract execution profiles

The routing contract SHALL support at least `routine`, `standard` and `complex` execution profiles, reachable either from an authored abstract start tier (`R1` -> `routine`, `R2` -> `standard`, `R3` -> `complex`) or from an explicit override. Concrete runtime model IDs and reasoning-effort settings SHALL live in versioned platform/runtime configuration or generated agent profiles rather than durable task artifacts.

Provider-local delegation, including a strong parent/supervisor, remains a supported execution capability, but a strong parent SHALL NOT be a mandatory entrypoint for every routing-enabled managed task: execution MAY begin directly on the tier-recommended executor. By default the supervisor SHALL implement routine/standard and complex work itself; delegating routine/standard implementation to a child executor SHALL happen only on an explicit delegation request. If work starts on a stronger-than-recommended session, the platform MAY down-route through the existing supported provider-local child path instead of requiring ceremonial re-delegation.

#### Scenario: Routine task stays on the supervisor by default

- **GIVEN** semantic preflight classifies a task as `routine` or `standard`
- **AND** no delegation is explicitly requested
- **WHEN** implementation begins
- **THEN** the supervisor implements the task itself under a supervisor-retained plan
- **AND** the user is not required to choose an executor manually

#### Scenario: Routine task is delegated cheaply

- **GIVEN** semantic preflight classifies a task as `routine` or `standard`
- **AND** delegation is explicitly requested and a supported cheaper executor is available
- **WHEN** implementation begins
- **THEN** the bounded implementation is delegated to the configured routine/standard executor

#### Scenario: Complex task stays on strong profile

- **GIVEN** semantic preflight classifies the task as `complex`
- **WHEN** implementation begins
- **THEN** the platform keeps or routes the work to the configured strong profile
- **AND** it does not require an unnecessary cheap-model attempt first

#### Scenario: R2 starts directly on the recommended executor

- **GIVEN** a managed task recommends `R2`
- **AND** the configured balanced provider-local executor is available
- **WHEN** execution starts directly on that executor
- **THEN** the task begins without first running Sol/Opus as a routing supervisor and without ceremonial strong-parent delegation
- **AND** normal containment, verification and publication invariants remain authoritative
- **AND** provider-local delegation remains available as a secondary capability if needed later

#### Scenario: Task opened on a stronger-than-recommended session

- **GIVEN** a managed task recommends `R2`
- **AND** execution is opened on a stronger-than-recommended provider-local session
- **WHEN** the platform evaluates the entrypoint
- **THEN** it MAY down-route through the existing supported provider-local delegation/fallback path
- **AND** normal containment and verification invariants remain authoritative

### Requirement: Execution path is fixed before task-content mutation

For a managed R2/R3 task, route preparation SHALL record an explicit execution plan before the first task-content change: either a delegated child executor, or supervisor-retained execution with its policy reason. The plan SHALL be derived from routing policy and the explicit delegation request, and SHALL be recorded separately from the authored recommended tier and from the actual execution outcome. A routine/standard route on a linked worktree SHALL be supervisor-retained with policy `balanced-parent` unless delegation is explicitly requested; a complex route SHALL be supervisor-retained with policy `complex-parent` and a route on a parent-only topology with policy `parent-only-topology`, regardless of a delegation request. Route preparation SHALL fail explicitly when task content has already diverged from the materialized managed package. Divergence SHALL cover the full task tree: deleting, moving or renaming a tracked implementation path into an excluded lifecycle location (.claude/ or openspec/changes/) SHALL count as a change of the source path.

#### Scenario: Default routine/standard route is supervisor-retained

- **WHEN** a routine/standard route on a linked worktree is prepared without an explicit delegation request
- **THEN** the routing record carries a supervisor-retained plan with policy `balanced-parent` and a task-content pre-snapshot
- **AND** the supervisor finalizes it with the retained outcome after implementation

#### Scenario: Policy requires a child executor

- **WHEN** a routine/standard route on a linked worktree is prepared with an explicit delegation request, including Codex dispatch
- **THEN** the routing record carries a delegated-child plan with a task-content pre-snapshot
- **AND** the authored start tier and the later actual executor remain separate recorded facts

#### Scenario: Policy permits supervisor execution

- **WHEN** a complex route, or a routine/standard route on a parent-only topology, is prepared
- **THEN** the routing record carries a supervisor-retained plan with the policy reason
- **AND** no child launch or escalation is recorded

#### Scenario: Content already diverged at routing

- **WHEN** task content outside the managed package has already changed before routing
- **THEN** route preparation fails naming the diverged paths
- **AND** no route is recorded

### Requirement: Routing mismatch fails at routing-adjacent lifecycle commands

The platform SHALL fail closed, through a shared read-only early gate, when a delegated-child plan has no open or completed delegation and task content differs from the pre-snapshot. The gate SHALL run in lifecycle status and finish, the check/test execution entrypoint and routing verification before any check executes, in addition to the archive gate. Records lacking a plan with no final execution outcome SHALL fail with an explicit re-route diagnostic rather than being accepted silently.

The platform SHALL also apply the same rules at the first implementation write: a platform-installed Claude Code pre-write hook SHALL deny a file write targeting an active managed task worktree outside lifecycle paths when no route is recorded yet, when the active record has no plan and no final execution outcome, or when the plan is a delegated child without an open or completed delegation. The denial SHALL name the required next command. A supervisor-retained plan or a real delegation SHALL allow the write with no additional step, and writes outside an active managed task SHALL NOT be affected. The platform SHALL install this hook idempotently into the integration checkout's machine-local agent settings for multi-agent platform projects and SHALL fail explicitly when those settings are malformed.

#### Scenario: Supervisor implements under a child-executor plan

- **GIVEN** a delegated-child plan with no open delegation
- **WHEN** the supervisor writes implementation content and runs status or a check entrypoint
- **THEN** the command fails before expensive checks, naming the diverged paths and the required delegation step

#### Scenario: First supervisor write under a child-executor plan

- **GIVEN** a delegated-child plan with no open delegation
- **WHEN** the supervisor attempts its first implementation file write through the agent write tool
- **THEN** the write is denied before the file changes
- **AND** the denial names the delegation step to run first

#### Scenario: First write before routing

- **GIVEN** an active managed task with no recorded route
- **WHEN** the supervisor attempts an implementation file write
- **THEN** the write is denied naming the routing command to run first

#### Scenario: Legitimate writes pass the write gate

- **GIVEN** a supervisor-retained plan, or a delegated-child plan with an open delegation
- **WHEN** an implementation file is written
- **THEN** the write gate allows it with no additional step

#### Scenario: Supervisor-retained plan is unaffected

- **GIVEN** a supervisor-retained plan declared at route time
- **WHEN** the supervisor changes task content and runs the same commands
- **THEN** the early gate passes

#### Scenario: Plan-less active record

- **GIVEN** an active managed route without a plan and without execution
- **WHEN** the early gate runs
- **THEN** it fails with a re-route diagnostic
