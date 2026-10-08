## ADDED Requirements

### Requirement: Execution path is fixed before task-content mutation

For a managed R2/R3 task, route preparation SHALL record an explicit execution plan before the first task-content change: either a delegated child executor, or supervisor-retained execution with its policy reason. The plan SHALL be derived from routing policy, not selected by the caller, and SHALL be recorded separately from the authored recommended tier and from the actual execution outcome. Route preparation SHALL fail explicitly when task content has already diverged from the materialized managed package. Divergence SHALL cover the full task tree: deleting, moving or renaming a tracked implementation path into an excluded lifecycle location (.claude/ or openspec/changes/) SHALL count as a change of the source path.

#### Scenario: Policy requires a child executor

- **WHEN** a routine/standard route on a linked worktree is prepared
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

### Requirement: A required child executor needs an open delegation before content changes

When the plan is a delegated child, the platform SHALL require an open delegation record before task content changes. For Claude, an explicit pre-launch step SHALL open the delegation, remain self-reported and SHALL NOT record a verified launch. Recording a Claude execution SHALL require that open delegation and SHALL be refused when no delegation was opened. Codex dispatch SHALL open a platform-observed delegation only once the child process has actually started. Any refusal or failure before launch, including containment preflight, runtime/login preflight and spawn errors, SHALL immediately record a closed attempt with outcome not-launched. Such attempts SHALL never authorize supervisor-written content, retained finalization or escalation.

#### Scenario: Correct delegated path

- **GIVEN** a delegated-child plan
- **WHEN** the supervisor opens the delegation, the child changes task content and the execution is recorded
- **THEN** early and archive routing gates pass with a claimed, self-reported execution and no verified-launch claim

#### Scenario: Execution recorded after the fact

- **GIVEN** a delegated-child plan with no open delegation and changed task content
- **WHEN** a Claude execution is recorded
- **THEN** recording is refused naming the missing delegation step

#### Scenario: Delegation opened late

- **GIVEN** a delegated-child plan whose task content has already diverged from the pre-snapshot
- **WHEN** a delegation is opened
- **THEN** it is refused

### Requirement: Routing mismatch fails at routing-adjacent lifecycle commands

The platform SHALL fail closed, through a shared read-only early gate, when a delegated-child plan has no open or completed delegation and task content differs from the pre-snapshot. The gate SHALL run in lifecycle status and finish, the check/test execution entrypoint and routing verification before any check executes, in addition to the archive gate. Records lacking a plan with no final execution outcome SHALL fail with an explicit re-route diagnostic rather than being accepted silently.

#### Scenario: Supervisor implements under a child-executor plan

- **GIVEN** a delegated-child plan with no open delegation
- **WHEN** the supervisor writes implementation content and runs status or a check entrypoint
- **THEN** the command fails before expensive checks, naming the diverged paths and the required delegation step

#### Scenario: Supervisor-retained plan is unaffected

- **GIVEN** a supervisor-retained plan declared at route time
- **WHEN** the supervisor changes task content and runs the same commands
- **THEN** the early gate passes

#### Scenario: Plan-less active record

- **GIVEN** an active managed route without a plan and without execution
- **WHEN** the early gate runs
- **THEN** it fails with a re-route diagnostic

### Requirement: Retained execution is declared up front and recovery never fabricates evidence

Recording a retained outcome SHALL require a supervisor-retained plan declared at route time and SHALL only finalize it with the containment postcheck. The platform SHALL NOT convert a delegated-child plan into retained execution after task content changed, SHALL NOT accept a Claude execution without an open delegation, and SHALL NOT permit an escalation to a supervisor-retained plan without a real recorded delegation or unchanged task content. No recovery path SHALL write a launch claim, retrospective delegation or escalation trigger that did not occur.

#### Scenario: Retained outcome after up-front plan

- **GIVEN** a supervisor-retained plan
- **WHEN** implementation completes and the retained outcome is recorded
- **THEN** the record is a real retained execution with a clean postcheck and the terminal gate passes

#### Scenario: Late switch to retention

- **GIVEN** a delegated-child plan with diverged task content and no delegation
- **WHEN** a retained outcome or escalation to retention is attempted
- **THEN** the operation is refused and the user must decide how to proceed

#### Scenario: Escalation after a real delegation

- **GIVEN** a recorded real delegation whose result was reviewed
- **WHEN** a recorded escalation with a concrete reason switches the plan to retention
- **THEN** the escalation is accepted and provenance keeps the delegation and the escalation distinct

#### Scenario: Unlaunched Codex attempt

- **WHEN** Codex is refused or fails before its child process starts
- **THEN** the attempt is closed with outcome not-launched and no open delegation remains
- **AND** subsequent supervisor writes fail the early gate and cannot authorize retention or escalation

#### Scenario: Lifecycle rename hides a source deletion

- **WHEN** a tracked implementation path is moved into an excluded lifecycle directory
- **THEN** divergence includes the source path for both staged and committed changes
- **AND** routing, late delegation and escalation cannot bypass the unchanged-content requirement
