## ADDED Requirements

### Requirement: Routine process review ownership is unambiguous during task preflight

Managed-task preflight SHALL NOT present the legacy local friction review surface as a routine action required from every current task agent when the configured routine review is performed by the periodic cloud workflow. Local review commands MAY remain available for recovery or diagnostics.

#### Scenario: Pending local friction exceeds the legacy threshold

- **GIVEN** routine periodic process review is configured
- **AND** several local friction events remain pending in the legacy local cursor
- **WHEN** `agent_doctor` runs for a managed task
- **THEN** it does not instruct the task agent to perform the routine local markdown review
- **AND** any message about the local surface is informational/recovery-oriented
- **AND** the weekly cloud review remains the documented routine cadence
