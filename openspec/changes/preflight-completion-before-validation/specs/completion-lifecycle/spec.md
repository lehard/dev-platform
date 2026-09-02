## ADDED Requirements

### Requirement: Observable completion blockers precede expensive validation

Dev Platform SHALL evaluate all safely observable read-only and cheap completion gates before starting expensive validation.

#### Scenario: One or more blockers are already observable

- **WHEN** cleanliness, OpenSpec/provenance, terminal state, freshness, scope, checkpoint or integration preflight reports a blocker
- **THEN** expensive validation does not start
- **AND** independently observable blockers are returned in one bounded actionable report

#### Scenario: Preflight is clear

- **WHEN** every current cheap completion gate passes
- **THEN** the canonical required checks run with unchanged verification semantics
- **AND** publication still performs required race-sensitive rechecks

### Requirement: Synchronous completion exposes bounded progress

The existing synchronous completion command SHALL expose its current lifecycle stage and test-group progress without requiring background polling processes.

#### Scenario: Completion runs for an extended period

- **WHEN** validation or protected publication remains in progress
- **THEN** the caller receives bounded stage progress and terminal output
- **AND** no new daemon, job queue or workflow engine is required
