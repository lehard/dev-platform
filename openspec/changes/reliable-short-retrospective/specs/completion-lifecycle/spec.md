# completion-lifecycle Specification Delta

## MODIFIED Requirements

### Requirement: Post-task retrospective truthfully accounts for meaningful lifecycle failures

Before non-trivial completion, the post-task retrospective SHALL consider bounded meaningful non-success evidence already produced by the current managed lifecycle, together with recorded manual workaround, non-default override, known-recurrence and observed-drift evidence attributed to the task. A `none` checkpoint SHALL NOT be accepted while any such mandatory signal remains without an explicit disposition as resolved-in-task, expected-behavior, already represented by durable friction evidence, or newly recorded. A new occurrence of an already open problem SHALL be preserved as recorded evidence and SHALL NOT be dismissed by disposition.

#### Scenario: Lifecycle failure exists but retrospective claims none

- **GIVEN** the current task produced a meaningful lifecycle failure
- **AND** no disposition or existing friction linkage accounts for it
- **WHEN** the executor attempts `checkpoint --result none`
- **THEN** completion rejects the checkpoint with an actionable retrospective instruction.

#### Scenario: Clean task has no meaningful friction

- **GIVEN** the retrospective reviews the current task and finds no meaningful unresolved/unrepresented lifecycle friction
- **WHEN** it records `none`
- **THEN** the checkpoint remains valid without additional ceremony.

#### Scenario: Recorded workaround is omitted

- **GIVEN** the task recorded a successful manual workaround event
- **WHEN** the executor attempts `checkpoint --result none` without a link or disposition
- **THEN** completion rejects the checkpoint naming the event.

#### Scenario: Expected failure is explained

- **GIVEN** a recorded signal describes an intentionally failing step
- **WHEN** the executor classifies it as expected-behavior and records `none`
- **THEN** the checkpoint is accepted without a new finding.

#### Scenario: Known recurrence cannot be dismissed

- **GIVEN** a recorded known-recurrence event for the task
- **WHEN** the executor classifies it with a dismissing disposition
- **THEN** the classification is refused and the event must be linked as a finding.
