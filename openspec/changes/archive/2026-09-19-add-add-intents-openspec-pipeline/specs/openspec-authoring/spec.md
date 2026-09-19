# openspec-authoring Specification Delta

## ADDED Requirements

### Requirement: OpenSpec proposal authoring can consume atomic intents

For work routed through the ADD/intents pipeline, OpenSpec authoring SHALL treat an intent as the normalized unit of pre-authoring input while using the approved ADD and current-system evidence as referenced constraints.

#### Scenario: Atomic intent is authored
- **WHEN** an intent is ready for OpenSpec
- **THEN** proposal authoring receives the business goal/context, the intent's bounded outcome/scope/non-goals/dependencies, and ADD/evidence references
- **AND** it does not require another broad architecture discovery pass

#### Scenario: One intent has an independent observable outcome
- **WHEN** an intent can be accepted, verified, delivered, or rolled back independently
- **THEN** it SHOULD be authored as its own OpenSpec change

#### Scenario: Several intents are inseparable
- **WHEN** several intents genuinely lack independent observable outcomes and are jointly required for one coherent change
- **THEN** they MAY be authored as one OpenSpec change
- **AND** the ordinary OpenSpec split test must justify that grouping rather than convenience alone

### Requirement: OpenSpec authoring preserves approved ADD decisions

OpenSpec authoring SHALL refine the implementation contract without silently replacing material system decisions already approved in ADD.

#### Scenario: Design remains within ADD
- **WHEN** OpenSpec `design.md` adds implementation detail consistent with the approved ADD
- **THEN** authoring proceeds normally

#### Scenario: Design requires a conflicting material decision
- **WHEN** OpenSpec authoring discovers that the approved ADD is insufficient or must materially change
- **THEN** the gap is returned to ADD/intent refinement before implementation
- **AND** proposal/design does not silently become the first place that new consequential architecture is decided

### Requirement: ADD/intents do not create a second OpenSpec lifecycle

After materialization, ordinary managed OpenSpec lifecycle rules SHALL govern implementation, verification, archive, and publication.

#### Scenario: Managed OpenSpec exists
- **WHEN** the intent has been materialized into an OpenSpec change
- **THEN** no ADD-specific implementation status, archive state, or second backlog is required
