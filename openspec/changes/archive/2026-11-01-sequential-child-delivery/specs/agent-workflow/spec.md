## ADDED Requirements

### Requirement: Sequential Requirement children are delivered one at a time

An intent set MAY declare sequential delivery with an explicit order of all its intents. Advance SHALL then deliver only the first not-Done child in that order through the single-child path and start the next only after it is Done. Without the declaration delivery SHALL be unchanged.

#### Scenario: Second child waits for the first
- **WHEN** a sequential Requirement's first child is in review
- **THEN** advance reports it and does not start the second child

### Requirement: Unchanged pre-authoring is rebound after own merges

For a sequential Requirement with stale pre-authoring, advance SHALL rebind snapshot, ADD, intents and handoffs to current main with a receipt and without re-approval when each changed source was changed only by its own delivered children or outside the remaining children's sources. Otherwise it SHALL stop naming paths, commits and what to re-approve.

#### Scenario: Own child changed a bound spec
- **WHEN** the only change to a bound spec came from a delivered child of the Requirement
- **THEN** advance rebinds, keeps the approval and starts the next child

#### Scenario: Foreign change to an affected spec
- **WHEN** another commit changed a spec a remaining child modifies
- **THEN** advance stops naming the spec and commit and the re-approval step
