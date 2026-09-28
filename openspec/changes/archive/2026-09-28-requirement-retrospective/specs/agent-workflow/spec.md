# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Business Requirement completion includes a bounded end-to-end retrospective

Before a non-trivial Business Requirement reaches terminal Done, Dev Platform SHALL require a truthful, fresh retrospective of the complete Requirement-first path: accepted Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery. New meaningful process findings SHALL use the existing friction/process-issue mechanism. A clean run MAY record a concise `none` result. The existing technical child post-task retrospective SHALL remain independently required and SHALL not be duplicated at parent level.

#### Scenario: Significant friction predates children

- **GIVEN** pre-authoring incurred repeated rework or a manual workaround before any child was materialized
- **WHEN** the parent retrospective is performed
- **THEN** the meaningful finding is routed through existing friction evidence and linked to the parent result
- **AND** clean child checkpoints do not erase it

#### Scenario: Cross-child friction survives clean children

- **GIVEN** children each finish cleanly but handoff or decomposition caused duplicate work or conflict between them
- **WHEN** the parent retrospective is performed
- **THEN** the cross-child finding is recorded without fabricating a child failure

#### Scenario: Clean parent and terminal gate

- **WHEN** the full path reveals no new meaningful finding
- **THEN** a concise `none` result suffices
- **AND** missing, stale, ambiguous, or unsupported retrospective evidence blocks parent Done with a recovery action

### Requirement: Every lifecycle stage participates in the shared process learning loop

A new lifecycle stage SHALL either route its meaningful process friction through the existing friction mechanism or make that evidence available to the nearest enclosing retrospective. Specialized reviews MAY contribute evidence but SHALL not introduce a separate improvement backlog or lifecycle.

#### Scenario: New pre-authoring stage detects friction

- **WHEN** a new stage is added before technical child execution
- **THEN** its meaningful friction is directly recorded or guaranteed to reach the parent Requirement retrospective
