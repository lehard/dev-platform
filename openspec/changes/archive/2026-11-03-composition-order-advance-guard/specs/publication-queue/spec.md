## ADDED Requirements

### Requirement: A re-admitted composition keeps its first queue slot

The queue SHALL order a Requirement composition by its first admission; a later admission of the same composition SHALL keep that ordering slot.

#### Scenario: Composition re-admitted after repair
- **GIVEN** compositions A then B were admitted
- **WHEN** A is re-admitted after integration repair
- **THEN** A stays ahead of B in the queue
