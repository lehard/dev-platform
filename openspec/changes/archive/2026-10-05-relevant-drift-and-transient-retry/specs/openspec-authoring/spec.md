## ADDED Requirements

### Requirement: Pre-authoring freshness follows bound source identities

An approved ADD, its intents and handoffs SHALL remain fresh when the integration branch moves without changing any source identity bound by their evidence snapshot. A change to a bound source SHALL make the dependent artifacts stale. The prepared revision SHALL be retained as provenance.

#### Scenario: Unrelated main commit
- **GIVEN** an approved ADD bound to a fresh snapshot
- **WHEN** main advances with changes to no bound source
- **THEN** the ADD, intents and handoffs remain fresh and no re-approval is required

#### Scenario: Bound source changes
- **WHEN** a source bound by the snapshot changes
- **THEN** the dependent ADD/intents/handoffs are stale and must be refreshed
