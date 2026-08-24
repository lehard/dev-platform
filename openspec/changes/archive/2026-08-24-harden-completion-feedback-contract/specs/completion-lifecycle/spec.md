## ADDED Requirements

### Requirement: Post-task retrospective truthfully accounts for meaningful lifecycle failures

Before non-trivial completion, the post-task retrospective SHALL consider bounded meaningful non-success evidence already produced by the current managed lifecycle. A `none` checkpoint SHALL NOT be accepted while a high-signal start, archive, publication, verification or comparable lifecycle failure remains without an explicit disposition as resolved-in-task, already represented by durable friction evidence, or newly recorded.

#### Scenario: Lifecycle failure exists but retrospective claims none

- **GIVEN** the current task produced a meaningful lifecycle failure
- **AND** no disposition or existing friction linkage accounts for it
- **WHEN** the executor attempts `checkpoint --result none`
- **THEN** completion rejects the checkpoint with an actionable retrospective instruction.

#### Scenario: Clean task has no meaningful friction

- **GIVEN** the retrospective reviews the current task and finds no meaningful unresolved/unrepresented lifecycle friction
- **WHEN** it records `none`
- **THEN** the checkpoint remains valid without additional ceremony.
