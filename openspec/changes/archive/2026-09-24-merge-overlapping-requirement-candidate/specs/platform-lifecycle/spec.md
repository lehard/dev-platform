# platform-lifecycle Specification Delta

## ADDED Requirements

### Requirement: Overlapping verified Requirement children use a protected merge candidate

When exact patch replay cannot combine a sequential verified child chain with newer main, the platform SHALL allow an isolated merge candidate whose two parents are exact current main and final verified child head. It SHALL preserve prior candidates and child heads, make conflict resolutions reviewable, run full validation and use protected PR publication before terminal reconciliation.

#### Scenario: Accepted spec changes overlap

- **GIVEN** current main and an archived child both extend the same accepted spec
- **WHEN** exact patch replay refuses the overlap
- **THEN** a separate candidate may merge the exact child chain and retain both accepted changes after reviewed resolution
- **AND** full checks and protected publication precede Done

#### Scenario: Merge provenance is not exact

- **GIVEN** a changed child branch, wrong merge parent, unexpected resolution path or unresolved conflict
- **WHEN** the candidate is prepared, finalized or published
- **THEN** it fails without taking over a prior candidate or changing terminal status
