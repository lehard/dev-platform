# agent-workflow Specification Delta

## MODIFIED Requirements

### Requirement: A Requirement can start and resume pre-authoring

Dev Platform SHALL provide one entrypoint that binds a Requirement identity to the pre-authoring orchestrator so analysis can begin and resume across sessions. The binding SHALL include the canonical values of Outcome, Context when present, Acceptance evidence when present, Exclusions when present, and target repository; it SHALL NOT bind only Outcome.

#### Scenario: Requirement bridges into pre-authoring

- **WHEN** `requirement_intake.py start` is given a Requirement reference
- **THEN** it extracts the Requirement's Outcome, Context, Acceptance evidence, Exclusions, and target repository from the Issue body
- **AND** initializes the pre-authoring orchestrator with a digestable canonical representation under the Requirement's stable identity

#### Scenario: Meaningful Requirement content changes before materialization

- **GIVEN** a Requirement has local pre-authoring artifacts but no canonical managed OpenSpec materialization
- **WHEN** a later start observes a changed Outcome, Context, Acceptance evidence, Exclusions, or target repository
- **THEN** it invalidates dependent derived pre-authoring state before reuse
- **AND** it does not continue design or handoff from the stale business meaning

#### Scenario: Requirement content is unchanged on resume

- **GIVEN** a Requirement's complete canonical business representation is unchanged
- **WHEN** pre-authoring resumes
- **THEN** existing snapshot, ADD, intent, and handoff artifacts remain eligible for their normal content/freshness checks
- **AND** the flow does not repeat semantic work solely because the session restarted

### Requirement: Intents are the normalized input to OpenSpec authoring

OpenSpec authoring SHALL consume atomic intents rather than using ADD directly as the normal specification unit. The handoff SHALL retain the complete accepted Requirement business context as bounded authoring input.

#### Scenario: Intent is ready for authoring

- **WHEN** an intent has bounded outcome, scope/non-goals, dependencies, and ADD/evidence references
- **THEN** its handoff includes the complete accepted Requirement business context plus the intent and approved ADD constraints
- **AND** authoring does not repeat broad system/design discovery merely to rediscover the approved delta

#### Scenario: OpenSpec authoring finds a material ADD conflict

- **WHEN** proposal/spec/design authoring requires changing an approved ADD decision
- **THEN** the flow returns to ADD/intent refinement
- **AND** does not silently override the approved design
