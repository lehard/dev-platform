# agent-workflow Specification Delta

## MODIFIED Requirements

### Requirement: A business requirement is a durable human-facing object distinct from OpenSpec

Dev Platform SHALL support recording an accepted business requirement as one Development Backlog Issue (`type:requirement`) containing only business-language content, with no OpenSpec proposal/design/tasks required at authoring time.

A newly created Requirement SHALL also carry exactly one `project:*` label and exactly one `priority:*` label resolved from the target repository's existing `[development_backlog]` configuration: `project_label`, and the explicitly requested priority or `default_priority`. No separate routing source or default SHALL be introduced. Missing or conflicting routing SHALL fail closed, and creation SHALL be reported successful only after a read-back verifies those labels.

#### Scenario: Requirement authored without OpenSpec
- **WHEN** a business requirement is accepted for fixation
- **THEN** it is recorded as one `type:requirement` Issue with outcome/context/acceptance-evidence/target-repository content
- **AND** no OpenSpec proposal, design, tasks, or technical decomposition is required to create it

#### Scenario: Requirement receives configured Backlog routing
- **GIVEN** the target repository configures `development_backlog.project_label` and `default_priority`
- **WHEN** `requirement_intake.py create` records a Requirement without an explicit priority
- **THEN** the Issue carries `type:requirement`, exactly the configured `project:*` label and exactly `priority:<default_priority>`
- **AND** creation succeeds only after reading those labels back from the Issue

#### Scenario: Requirement routing is missing or conflicting
- **WHEN** the target repository's project label is not configured in the creating checkout, the Backlog repository disagrees with configuration, or a configured label is unavailable
- **THEN** creation stops before any Issue is created
- **AND WHEN** a created Issue reads back with a different `project:*` or `priority:*` label
- **THEN** the exact Issue is reported and fixation is not reported successful
