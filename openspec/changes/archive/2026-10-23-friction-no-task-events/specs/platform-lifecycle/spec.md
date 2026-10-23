## MODIFIED Requirements

### Requirement: Friction events carry resolvable task attribution

New friction events SHALL record an explicit task when given, otherwise the current task branch. An event recorded with neither, from an integration checkout or an unknown or detached branch, SHALL be classified `no-task`; such a checkout SHALL NOT be assumed to be a task. A legacy task-less event with no other attribution evidence whose recorded branch is a non-task name SHALL be read as `no-task` without rewriting history. An operator SHALL be able to classify a recorded event as `no-task` with a reason through an explicit append-only operation; an explicit `no-task` and an explicit task attribution of the same event SHALL conflict and fail. A `no-task` event SHALL NOT be a signal of, nor block, any task or Requirement retrospective, and SHALL be listed as such in review and checkpoint output. Retrospective selection SHALL attribute a legacy event whose task is empty by its recorded branch or source issue without rewriting or duplicating history. An event that has no task, no usable branch, source issue or attribution and no `no-task` classification SHALL be reported as an explicit ambiguity, SHALL NOT be assigned to the task under review, and SHALL make both the automated and the manual task and Requirement checkpoints refuse with the event ids and the attribution commands until it is attributed or classified.

#### Scenario: Event lost its task but kept branch and source issue

- **GIVEN** a recorded event has an empty task and a branch equal to the task under review
- **WHEN** the retrospective selects mandatory signals
- **THEN** the event is included as an inferred-attribution signal and must be explained
- **AND** the stored event is not modified

#### Scenario: Event recorded outside a task does not block another candidate

- **GIVEN** an event is recorded from the integration checkout while candidate A is in progress
- **WHEN** the automated retrospective of candidate B runs
- **THEN** the event is classified `no-task`, is not a signal of B and does not block it

#### Scenario: Operator classifies an event as not related to any task

- **WHEN** the operator runs the explicit no-task attribution with a reason
- **THEN** the classification is appended without changing the event
- **AND** the review output lists the event as `no-task` with that reason
- **AND** a later explicit task attribution of the same event fails

#### Scenario: Event cannot be attributed

- **GIVEN** a recent event has an empty task, no usable branch, source issue or attribution, and no `no-task` classification
- **WHEN** a manual or automated checkpoint runs
- **THEN** it refuses, naming the event and the task and no-task attribution commands
- **AND** the event is not assigned to the task under review
