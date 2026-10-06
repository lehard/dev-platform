## ADDED Requirements

### Requirement: Parallel lifecycle acceptance is reproducible in a sandbox

The platform SHALL provide a deterministic offline scenario in a disposable repository that drives several parallel candidates through review, at least one repair, finalization and sequential integration while main moves, using the real coordinator and worker code with fake provider and GitHub adapters.

#### Scenario: Scenario runs
- **WHEN** the scenario is executed twice
- **THEN** both runs merge every candidate and record the same lifecycle transitions without manual steps
- **AND** a finalized managed candidate whose integration repair changed its content is re-reviewed against its archived artifacts and returns through finalization to integration
