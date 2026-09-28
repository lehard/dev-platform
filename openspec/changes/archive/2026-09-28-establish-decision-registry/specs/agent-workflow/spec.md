# agent-workflow Specification Delta

## MODIFIED Requirements

### Requirement: Domain refinement does not create a competing implementation contract

Accepted refinement SHALL be recorded in existing managed OpenSpec artifacts and SHALL NOT require a parallel context, ADR, status or planning ledger as an authoritative implementation source. A repository decision registry MAY preserve consequential historical rationale and revisit conditions, but SHALL NOT override OpenSpec's accepted executable behavior or active deltas.

#### Scenario: Refinement is complete

- **WHEN** material ambiguity is resolved
- **THEN** the accepted behavior is incorporated into proposal/spec/design as appropriate
- **AND** materialized OpenSpec remains canonical for implementation and verification
- **AND** a relevant historical decision record may retain the rationale without becoming a second implementation contract
