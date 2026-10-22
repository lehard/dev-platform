## ADDED Requirements

### Requirement: Ordinary lifecycle commands do not retry friction routing

`start`, `doctor`, `finish` and Requirement `advance` SHALL NOT invoke GitHub routing of locally retained friction events and SHALL NOT wait on it or print a routing-retry warning. Retained events SHALL remain pending and SHALL be retried only by the explicit `agent_friction.py route-pending` command.

#### Scenario: Doctor with pending routing
- **GIVEN** the local friction log holds an event whose GitHub routing is pending
- **WHEN** `doctor` (or `start`, which runs it) executes
- **THEN** it does not run `route-pending`
- **AND** it prints no friction routing retry warning

#### Scenario: Finish with pending routing
- **GIVEN** a pending friction route
- **WHEN** `finish` or `advance` reaches its completion preflight
- **THEN** it does not run `route-pending` and does not wait on GitHub routing

#### Scenario: Explicit retry
- **WHEN** an operator runs `agent_friction.py route-pending`
- **THEN** pending events are retried and the JSON result reports routed, failed and withheld counts

### Requirement: Routed coordinator events name their reason and candidate

A coordinator lifecycle event (`coordinator-review-repair`, `coordinator-retry`, `coordinator-integration-repair`, `lifecycle-blocked-escalation`, `lifecycle-validation-failure`, or any event attributed to the coordinator) SHALL carry a bounded `reason` and a `candidate` naming the task branch, the PR number when one exists, and the head. The publication coordinator SHALL take the reason from the transition's named red gate and SHALL fail the transition explicitly with a named error when the gate is missing or explains nothing; a `blocked-retryable` transition without a red gate waits on exact-head required checks, is not a failed gate and SHALL record no friction event. Other producers SHALL fail explicitly with a named error rather than record such an event without them. The router SHALL render the reason and candidate in the published issue or comment, and SHALL NOT route a coordinator event that lacks either; such an event SHALL be recorded locally as `withheld` with the missing field named and SHALL NOT be retried.

#### Scenario: Coordinator retry is routed with its cause
- **GIVEN** the coordinator schedules a bounded retry of PR candidate 42 at head `abc` because a gate was unavailable
- **WHEN** the event is routed
- **THEN** the published body names the candidate (task branch, PR 42, head `abc`) and the reason

#### Scenario: Validation failure carries the failing check
- **WHEN** `finish` records `lifecycle-validation-failure`
- **THEN** the event reason names the failure class and failing check from the selector descriptor
- **AND** the candidate names the current branch and head

#### Scenario: Faceless coordinator event
- **GIVEN** a locally retained coordinator event with no reason or no candidate
- **WHEN** `route-pending` runs
- **THEN** no GitHub issue or comment is created for it
- **AND** its route is recorded as `withheld` naming the missing field and it is not retried

#### Scenario: Producer without a reason
- **WHEN** the coordinator emits a friction transition into review repair, integration repair or escalation without a named red gate, or with a red gate that has no cause or evidence
- **THEN** recording fails with an error naming the PR and the state

#### Scenario: Waiting on required checks is not friction
- **WHEN** the coordinator records `blocked-retryable` without a red gate while the candidate waits on its exact-head required checks
- **THEN** the transition is published and no friction event is recorded
