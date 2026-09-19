# project-context Specification Delta

## ADDED Requirements

### Requirement: Project context can feed reusable evidence snapshots

Dev Platform SHALL support derived Project Evidence Snapshots that consume canonical repository/project context without replacing it.

#### Scenario: Reviewed project context exists
- **WHEN** a snapshot projection needs product/domain/architecture knowledge
- **THEN** relevant `docs/context/` content may be used as evidence with stable source identity
- **AND** the snapshot remains derived/non-authoritative

#### Scenario: Project context changes
- **WHEN** a source identity used by a projection changes
- **THEN** the affected projection becomes stale
- **AND** unrelated projections are not invalidated unless their dependency evidence also changed

### Requirement: Snapshot facts preserve evidence and uncertainty

Derived semantic facts SHALL carry enough provenance to trace them to bounded sources and SHALL distinguish facts from conflicts/unknowns.

#### Scenario: Sources disagree materially
- **WHEN** authoritative-looking sources support conflicting current-system claims
- **THEN** the snapshot records the conflict or escalation need
- **AND** does not promote one unsupported interpretation to canonical project context
