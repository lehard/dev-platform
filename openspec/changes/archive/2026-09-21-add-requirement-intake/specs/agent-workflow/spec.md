# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: A business requirement is a durable human-facing object distinct from OpenSpec

Dev Platform SHALL support recording an accepted business requirement as one Development Backlog Issue (`type:requirement`) containing only business-language content, with no OpenSpec proposal/design/tasks required at authoring time.

#### Scenario: Requirement authored without OpenSpec
- **WHEN** a business requirement is accepted for fixation
- **THEN** it is recorded as one `type:requirement` Issue with outcome/context/acceptance-evidence/target-repository content
- **AND** no OpenSpec proposal, design, tasks, or technical decomposition is required to create it

### Requirement: A Requirement can start and resume pre-authoring

Dev Platform SHALL provide one entrypoint that binds a Requirement identity to the pre-authoring orchestrator (#129) so analysis can begin and resume from it across sessions.

#### Scenario: Requirement bridges into pre-authoring
- **WHEN** `requirement_intake.py start` is given a Requirement reference
- **THEN** it extracts the requirement's outcome/target-repository from the Issue body
- **AND** initializes the pre-authoring orchestrator with that content under the Requirement's stable identity

### Requirement: Internal managed OpenSpec changes remain linked to their parent Requirement

Dev Platform SHALL link every internal managed OpenSpec change produced from a Requirement's pre-authoring back to that Requirement, and SHALL label it distinctly from the Requirement itself.

#### Scenario: A ready intent produces a linked internal change
- **WHEN** a handoff-ready intent is materialized into a managed OpenSpec Issue
- **THEN** that Issue is labeled `type:internal-change`
- **AND** the parent Requirement's children block records a reference to it
- **AND** the child Issue records a back-reference to its parent Requirement

#### Scenario: One Requirement produces multiple internal changes
- **WHEN** a Requirement's pre-authoring yields more than one ready intent
- **THEN** each materializes as its own linked `type:internal-change` Issue
- **AND** the main human-facing board is not required to treat them as unrelated top-level work

### Requirement: Requirement progress is derived, not duplicated

Dev Platform SHALL derive a Requirement's aggregate progress by reading its linked children's existing Development Backlog Project status, and SHALL NOT introduce a second status field, backlog, or state machine to track it.

#### Scenario: Aggregate reflects real child lifecycle
- **WHEN** `requirement_intake.py aggregate` is run for a Requirement with linked children
- **THEN** it reports a status derived only from each child's current Project status
- **AND** it writes no separate status value that could diverge from that source of truth

#### Scenario: Unreadable child status fails closed
- **WHEN** a linked child's Project status cannot be read
- **THEN** the aggregate reports that child as unknown rather than assuming it is done or in progress
