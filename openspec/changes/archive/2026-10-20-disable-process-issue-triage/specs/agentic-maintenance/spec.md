## REMOVED Requirements

### Requirement: Process issue triage reuses a maintained upstream pattern
**Reason**: The owner decided on 2026-10-19 to disable event-driven process-issue triage; it repeatedly exhausted its budget and produced failure-report noise.
**Migration**: Process and friction issues are reviewed by the periodic Process Health Review; see "Event-driven process triage is not installed".

### Requirement: Cloud agents are read-only with constrained safe outputs
**Reason**: Its only scenario described the removed process-issue triage workflow.
**Migration**: Replaced by "Cloud maintenance agents are read-only with constrained safe outputs", which applies the same constraint to every installed cloud maintenance workflow.

## ADDED Requirements

### Requirement: Cloud maintenance agents are read-only with constrained safe outputs

The v1 process-maintenance agent job SHALL NOT receive unrestricted repository write access. GitHub mutations SHALL occur only through explicitly declared and bounded `safe-outputs`.

#### Scenario: Cloud maintenance workflow executes

- **WHEN** an installed cloud maintenance workflow runs
- **THEN** the agent may inspect repository and issue context
- **AND** may request only its declared, bounded safe outputs
- **AND** cannot edit code, create an implementation pull request, approve, merge, or directly mutate repository contents

### Requirement: Event-driven process triage is not installed

By owner decision of 2026-10-19, the platform SHALL NOT install an agentic workflow that triages process issues on issue events. Process and friction issues SHALL be reviewed by the periodic Process Health Review. Platform documentation describing agentic workflows SHALL state that event-driven triage is disabled by owner decision and name the Process Health Review as the review path.

#### Scenario: Process label is added

- **WHEN** a maintainer adds the `process` label to an issue, or any other issue event occurs
- **THEN** no agentic triage workflow run starts
- **AND** no triage issue or comment, including a budget-exhaustion or failure report, is created

#### Scenario: Agentic workflow sources are validated

- **WHEN** the agentic workflow validation and tests run
- **THEN** they fail if a `process-issue-triage` source or lock exists or an agentic workflow source triggers on `issues` events
