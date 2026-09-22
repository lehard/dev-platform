# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Requirement pre-authoring is proportional and provider-neutral

Dev Platform SHALL select and record the least ceremonial safe pre-authoring depth from the complete Requirement and scoped repository evidence. The selection SHALL compose with the existing provider-neutral routing policy and SHALL NOT introduce a second router or provider-specific lifecycle.

#### Scenario: Deterministic work bypasses semantic design stages

- **WHEN** a complete Requirement and its bounded repository evidence yield a deterministic action with no material design delta
- **THEN** the flow records the deterministic depth and next action without invoking a model or requiring ADD/intents
- **AND** a resumed run can reuse that recorded decision while its bindings remain fresh

#### Scenario: Bounded evidence work uses the routine read-only path

- **WHEN** the flow needs bounded evidence extraction but no material design decision
- **THEN** it requests only the scoped projections needed for that extraction
- **AND** it records the existing routine read-only route rather than escalating to design routing

#### Scenario: Material design work proceeds through ADD and intents

- **WHEN** scoped evidence leaves a genuine architecture, behavior, compatibility, or execution design delta
- **THEN** the flow records that reason and requires ADD/intents under the existing R2 default
- **AND** it escalates to R3 only for a documented existing hard trigger

#### Scenario: Explicit skip and scoped evidence remain resumable

- **WHEN** ADD/intents are safely skipped or a matching scoped projection is already fresh
- **THEN** the flow persists a bounded receipt with its source/evidence bindings
- **AND** a changed binding invalidates only the decision and artifacts that depended on it
