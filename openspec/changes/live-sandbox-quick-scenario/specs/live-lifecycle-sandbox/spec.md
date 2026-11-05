## Purpose

Prove the lifecycle on real GitHub in a private sandbox running the real queue at an exact platform head, isolated from production resources.

## ADDED Requirements

### Requirement: Sandbox runs the real queue at an exact platform head

Dev Platform SHALL provide a private sandbox repository in source mode whose default branch carries a reproducible snapshot of an exact platform head over a fixture project with its own CI and checks. The sandbox SHALL NOT be rendered through Copier and SHALL NOT be an entry of the production managed project registry.

#### Scenario: Snapshot is installed

- **WHEN** the runner installs a platform head into the sandbox
- **THEN** the sandbox default branch carries that head's queue, worker and lifecycle code
- **AND** the installed head is recorded and readable from the sandbox

#### Scenario: Rollout runs

- **WHEN** a managed rollout reads the production registry
- **THEN** the sandbox is not a target

### Requirement: Sandbox is isolated from production resources

The sandbox SHALL use a dedicated GitHub App installed only on it, its own operator configuration and registry and its own Backlog binding. Production App keys and provider tokens SHALL NOT be stored in it. The runner SHALL refuse before any write when the target repository is not the configured sandbox or the configuration names a production resource.

#### Scenario: Runner is pointed at another repository

- **GIVEN** the configured target is not the sandbox
- **WHEN** a run or reset starts
- **THEN** it stops with an error naming the target
- **AND** nothing is written to any repository

### Requirement: Reset restores a clean start without rewriting history

Each run SHALL start with a reset, also available as a command: close open PRs and Issues of the sandbox, delete work branches, and commit the baseline tree forward on main without force-push. A second concurrent run SHALL be refused. A failed run SHALL NOT prevent the next one.

#### Scenario: Previous run failed midway

- **GIVEN** a previous run left an open PR, a claim and a work branch
- **WHEN** the next run starts
- **THEN** reset leaves no open PR and no work branch
- **AND** the scenarios run on new PR numbers

### Requirement: Scenarios use documented entrypoints and fail by step

One runner command SHALL run all or selected scenarios on real GitHub through documented platform entrypoints only and SHALL NOT change labels, lifecycle comments or queue records directly. Each scenario SHALL check its final GitHub state. A failed or timed-out step SHALL exit non-zero naming scenario, step and observed state. A known failure SHALL be reported as a failure.

#### Scenario: Step reaches a dead end

- **GIVEN** a step does not reach its expected state within its limit
- **WHEN** the scenario evaluates that step
- **THEN** the run fails naming the scenario, the step and the observed state

### Requirement: Quick task scenario reaches MERGED

The scenarios SHALL include a quick task driven from start through finish and the sandbox queue to a MERGED pull request, with no step outside documented entrypoints.

#### Scenario: Quick task runs

- **WHEN** the quick task scenario runs on the sandbox
- **THEN** its pull request is MERGED by the sandbox coordinator App
- **AND** the change is on the sandbox main branch
