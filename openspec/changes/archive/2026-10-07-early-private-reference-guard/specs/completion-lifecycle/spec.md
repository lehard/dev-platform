## ADDED Requirements

### Requirement: Private-reference guard precedes child archive
For checkouts with private lineage enabled, the lifecycle SHALL run the existing private Backlog reference guard over the current public candidate before archive launches independent review, selected checks, writes automated evidence, or mutates OpenSpec. This SHALL apply to ordinary archive and coordinator finalization. A missing configured guard or failed guard SHALL stop explicitly with actionable diagnostics. Checkouts without private lineage enabled SHALL retain their existing archive behavior.

#### Scenario: Private reference in child proposal or design
- **GIVEN** a privacy-enabled child candidate has a supported direct private Issue reference in proposal.md or design.md
- **WHEN** archive is requested
- **THEN** archive fails before review, expensive checks, evidence writes and OpenSpec mutation
- **AND** diagnostic categories and opaque fingerprints guide repair without exposing private identifiers

#### Scenario: Private reference in inherited archived artifact
- **GIVEN** a privacy-enabled candidate contains a supported private Issue reference in an archived proposal or design
- **WHEN** archive is requested
- **THEN** the current candidate guard blocks before archive mutation

#### Scenario: Configured guard unavailable
- **GIVEN** private lineage is enabled and the repository guard is missing
- **WHEN** archive is requested
- **THEN** archive fails explicitly and does not substitute another scanner or proceed

#### Scenario: Clean or opted-out child
- **WHEN** the configured guard passes or private lineage is disabled
- **THEN** archive continues through its existing required verification gates

### Requirement: Private-reference guard precedes shared candidate full checks
For checkouts with private lineage enabled, the shared Requirement publisher SHALL run the existing current-candidate private-reference guard before local full validation and public publication for complete and draft candidates. The existing publication-time guard SHALL remain in place to catch changes after the early gate.

#### Scenario: Shared candidate contains private reference
- **GIVEN** a shared candidate contains a supported direct private Issue reference in an archived child artifact
- **WHEN** the shared publisher runs
- **THEN** it fails before full validation or public mutation with non-disclosing repair guidance

#### Scenario: Clean shared candidate
- **WHEN** the early guard passes for a complete shared candidate
- **THEN** the full mandatory checks still run and protected publication retains its privacy recheck
