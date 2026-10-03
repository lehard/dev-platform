# agent-workflow Specification Delta

## MODIFIED Requirements

### Requirement: Business Requirement completion includes a bounded end-to-end retrospective

Before a non-trivial Business Requirement reaches terminal Done, Dev Platform SHALL require a truthful, fresh retrospective of the complete Requirement-first path: accepted Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery. New meaningful process findings SHALL use the existing friction/process-issue mechanism. A clean run MAY record a concise `none` result. The existing technical child post-task retrospective SHALL remain independently required and SHALL not be duplicated at parent level.

The parent review SHALL inspect meaningful successful manual workarounds, non-default or override actions, manual state changes, recurrences of already open process problems, and observed material drift even when another operator or lifecycle owns the state. `none` requires this bounded factual path review and remains concise on a clean path.

The parent review SHALL use the same mandatory-signal set, dispositions and evidence-gap rules as the task retrospective for signals attributed to the Requirement during pre-authoring and between children, including legacy events attributed by branch or source issue, and SHALL name an unreadable evidence source instead of treating it as clean.

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

#### Scenario: Open issue recurs in Requirement delivery

- **GIVEN** a known open process issue is encountered again while delivering a Requirement
- **WHEN** the parent review runs
- **THEN** the recurrence is retained as new occurrence evidence linked to the existing problem
- **AND** the parent does not claim `none` merely because the issue was already known.

#### Scenario: Operator-owned drift is observed

- **WHEN** the agent observes material state drift outside its own ownership during the Requirement path
- **THEN** the review considers it as process evidence regardless of who may repair it.

#### Scenario: Requirement signal is unexplained

- **GIVEN** a workaround event is attributed to the Requirement and not linked or classified
- **WHEN** the parent checkpoint is attempted with `none`
- **THEN** it is refused naming the event.
