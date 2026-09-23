# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Confirmed handoff materialization has a successful machine-readable CLI result

Dev Platform SHALL return a successful machine-readable CLI result only when the exact internal managed change and its parent Requirement linkage are both confirmed.

#### Scenario: Confirmed materialization serializes successfully

- **GIVEN** a validated ready handoff materializes an exact linked child
- **WHEN** the CLI returns its result
- **THEN** it exits zero with parseable JSON identifying the Requirement and child
- **AND** an exact retry reports that same child without duplicate durable work
