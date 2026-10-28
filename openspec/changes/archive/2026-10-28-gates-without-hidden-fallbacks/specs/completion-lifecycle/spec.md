## MODIFIED Requirements

### Requirement: Observable completion blockers precede expensive validation

Dev Platform SHALL evaluate all safely observable read-only and cheap completion gates, including, for checkouts with private lineage enabled, the existing private Backlog reference guard over the current public candidate, before starting expensive validation. For checkouts with private lineage enabled the same guard SHALL still run at publication time to cover changes after preflight, and a missing guard script SHALL be a blocker naming it. For checkouts without private lineage enabled the guard SHALL NOT run and completion and publication SHALL report that it is not applicable by configuration.

#### Scenario: One or more blockers are already observable

- **WHEN** cleanliness, OpenSpec/provenance, terminal state, freshness, scope, checkpoint, privacy or integration preflight reports a blocker
- **THEN** expensive validation does not start
- **AND** independently observable blockers are returned in one bounded actionable report

#### Scenario: Preflight is clear

- **WHEN** every current cheap completion gate passes
- **THEN** the canonical required checks run with unchanged verification semantics
- **AND** publication still performs required race-sensitive rechecks

#### Scenario: Private reference in candidate evidence

- **GIVEN** private lineage is enabled
- **AND** a candidate verification artifact contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the candidate-file surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Private reference in new commit message

- **GIVEN** private lineage is enabled
- **AND** a new candidate commit message contains a supported direct private Backlog Issue reference
- **WHEN** completion preflight runs
- **THEN** it reports the commit-message surface with non-disclosing diagnostics and opaque-lineage repair guidance
- **AND** expensive validation has not started

#### Scenario: Clean candidate passes preflight

- **GIVEN** private lineage is enabled
- **WHEN** no supported public candidate surface contains a direct private reference
- **THEN** completion proceeds to the existing required validation without another privacy mechanism
- **AND** publication still applies the fail-closed current-candidate guard

#### Scenario: Guard script missing with private lineage enabled

- **GIVEN** private lineage is enabled
- **AND** `scripts/check_private_backlog_refs.py` is absent
- **WHEN** completion preflight or publication runs
- **THEN** it reports a blocker naming the missing guard script
- **AND** nothing is published

#### Scenario: Private lineage not enabled

- **GIVEN** private lineage is not enabled
- **WHEN** completion preflight or publication runs
- **THEN** the guard does not run
- **AND** the run reports that the private-reference guard is not applicable by configuration
