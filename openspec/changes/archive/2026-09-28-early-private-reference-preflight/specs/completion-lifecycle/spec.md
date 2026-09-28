# completion-lifecycle Specification Delta

## MODIFIED Requirements

### Requirement: Observable completion blockers precede expensive validation

Dev Platform SHALL evaluate all safely observable read-only and cheap completion gates, including the existing private Backlog reference guard over the current public candidate, before starting expensive validation. The same guard SHALL still run at publication time to cover changes after preflight.

#### Scenario: One or more blockers are already observable

- **WHEN** cleanliness, OpenSpec/provenance, terminal state, freshness, scope, checkpoint, privacy or integration preflight reports a blocker
- **THEN** expensive validation does not start
- **AND** independently observable blockers are returned in one bounded actionable report

#### Scenario: Preflight is clear

- **WHEN** every current cheap completion gate passes
- **THEN** the canonical required checks run with unchanged verification semantics
- **AND** publication still performs required race-sensitive rechecks

#### Scenario: Private reference in candidate evidence

- **GIVEN** a candidate verification artifact contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the candidate-file surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Private reference in new commit message

- **GIVEN** a new candidate commit message contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the commit-message surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Clean candidate passes preflight

- **WHEN** no supported public candidate surface contains a direct private reference
- **THEN** completion proceeds to the existing required validation without another privacy mechanism
- **AND** publication still applies the fail-closed current-candidate guard
