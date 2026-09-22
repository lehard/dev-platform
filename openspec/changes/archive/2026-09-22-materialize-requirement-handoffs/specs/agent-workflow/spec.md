# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Ready Requirement handoffs materialize idempotently into linked internal changes

Dev Platform SHALL materialize a validated ready handoff through the existing managed-task intake boundary and SHALL return success only when the exact internal managed change and its parent Requirement linkage are both confirmed.

#### Scenario: A ready handoff creates one linked internal change

- **WHEN** a validated ready handoff is materialized for a Requirement
- **THEN** the adapter renders the existing managed-task package contract and creates or exactly reuses one internal managed Issue
- **AND** it immediately confirms the parent-to-child and child-to-parent linkage before reporting success

#### Scenario: Retry repairs an interrupted linkage without duplication

- **GIVEN** a prior materialization created its exact child but did not complete linkage
- **WHEN** the same handoff is retried
- **THEN** the adapter resolves that exact child by stable handoff identity and repairs the missing link
- **AND** it does not create another managed Issue or canonical OpenSpec change

#### Scenario: Invalid or ambiguous materialization fails safely

- **WHEN** handoff bindings are invalid or candidate provenance is ambiguous
- **THEN** materialization stops with actionable failure evidence
- **AND** it does not report a partial Issue/link pair as successful
