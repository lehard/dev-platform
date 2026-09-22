# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Requirement progress is a derived human-facing projection

Dev Platform SHALL expose the Requirement's pre-authoring and child-execution progress as a recomputable read-through projection. It SHALL NOT create or mutate a second manual Requirement lifecycle state.

#### Scenario: Pre-authoring and readiness are visible before children exist

- **WHEN** a Requirement has current local orchestrator evidence and no linked internal child
- **THEN** the projection distinguishes active pre-authoring/design, a human decision gate when applicable, and implementation readiness
- **AND** it identifies the evidence used for that display stage

#### Scenario: Linked child lifecycle determines implementation and completion

- **WHEN** a Requirement has linked internal changes with authoritative lifecycle observations
- **THEN** the projection reports implementation while required children are active and completion only when all required children are complete
- **AND** it keeps internal changes out of the primary human-facing Project view

#### Scenario: Unreadable or contradictory source state is not optimistic

- **WHEN** required orchestrator or linked-child source state is missing, stale, unreadable, contradictory, or explicitly blocked
- **THEN** the projection reports blocked or unknown with the diagnostic reason
- **AND** it does not present the Requirement as ready or complete
