# public-distribution Specification Delta

## ADDED Requirements

### Requirement: Public source and output guard protects private managed task identifiers

The platform SHALL prevent supported references to private managed task Issues from entering current public source, report text, and publication artifacts. The check SHALL use bounded configured/private-provenance context and SHALL fail closed when a managed source could be private but cannot be classified. It SHALL not claim that a current-tree scan proves old Git history clean.

#### Scenario: Private task reference in tracked source

- **GIVEN** a tracked public candidate file contains a supported private task Issue reference
- **WHEN** public validation runs before publication
- **THEN** it fails with a bounded path and safe reason without reproducing private content

#### Scenario: Opaque managed lineage is present

- **GIVEN** a public managed archive stores only an opaque lineage handle
- **WHEN** current source is audited
- **THEN** that archive is permitted if its private mapping was verified through an authorized read

#### Scenario: Historical commits remain

- **WHEN** current public source and outputs pass the privacy guard
- **THEN** the receipt identifies the checked current surfaces and does not claim that old Git commits were erased
