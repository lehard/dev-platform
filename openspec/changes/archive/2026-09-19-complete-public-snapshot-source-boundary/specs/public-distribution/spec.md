## ADDED Requirements

### Requirement: Fresh public snapshot is a self-contained canonical source repository

A successful public snapshot SHALL contain every repository path required by its own public README, CI workflows, platform validation commands, and accepted specification contract. Sanitization SHALL NOT achieve a clean result by removing source-of-truth or verification material that the packaged repository itself depends on.

#### Scenario: CI references tests and accepted specifications
- **GIVEN** the packaged CI invokes repository tests, OpenSpec validation, upgrade smoke, or other checked-in verification entrypoints
- **WHEN** the public snapshot is prepared
- **THEN** the corresponding required scripts, tests, OpenSpec configuration, and accepted `openspec/specs/` content are present in the snapshot
- **AND** the CI workflow does not reference paths deliberately excluded from the snapshot.

#### Scenario: README links to repository-owned source paths
- **WHEN** a packaged README or public doc links to a repository-owned path that is part of the documented product surface
- **THEN** that path exists in the extracted snapshot
- **OR** the documentation is deliberately updated so the link is not part of the public contract.

### Requirement: Historical evidence may be excluded only by explicit non-product policy

Maintenance/history-only material MAY be excluded from the fresh public source snapshot when it is not required by runtime, CI, accepted specifications, public documentation, or upgrade/release verification. Exclusion SHALL be narrow and documented.

#### Scenario: Archived historical OpenSpec changes contain private operator evidence
- **WHEN** old `openspec/changes/archive/` records contain project-specific historical references
- **AND** those archives are not required for the public repository's current CI, accepted specs, release tooling, or user documentation
- **THEN** the archive subtree may be explicitly excluded from the fresh-history product snapshot
- **AND** current accepted `openspec/specs/` and required OpenSpec configuration remain present.

### Requirement: Extracted snapshot proves source completeness

The platform SHALL run a bounded source-completeness smoke against the extracted public snapshot before cutover readiness is declared.

#### Scenario: Snapshot smoke succeeds
- **WHEN** the deterministic snapshot is extracted into a clean temporary directory
- **THEN** required README/internal links checked by the repository are resolvable
- **AND** every repository-owned path invoked by packaged CI exists
- **AND** the public test/spec/validation entrypoints selected for the product snapshot execute successfully or are proven by the same repository-owned checks used in CI
- **AND** the smoke records the exact source revision and snapshot digest.

#### Scenario: Packaged workflow references an excluded path
- **WHEN** the extracted snapshot contains a CI or public validation command that references a missing excluded repository path
- **THEN** snapshot readiness fails before canonical repository cutover.

### Requirement: Sanitization detects project-specific compatibility material

Public-distribution audit SHALL detect prohibited live compatibility material tied to the current operator's downstream projects even when the material is expressed as project names, project-specific constants, hash names, migration functions, messages, or code branches rather than an `owner/repo` reference.

#### Scenario: Public candidate contains project-specific rollout shim
- **WHEN** a packaged candidate contains a compatibility constant, function, message, branch, fixture, or migration payload whose semantics are specific to a real, named live personal downstream project
- **THEN** the audit blocks the snapshot until the material is removed, generalized with synthetic semantics, or relocated to an external operator-owned compatibility surface.

#### Scenario: Generic synthetic fixture remains
- **WHEN** a test or example uses synthetic project identities solely to verify generic rollout behavior
- **THEN** it may remain in the public product
- **AND** it does not encode private repository names, private migration hashes, or operator-specific production payloads.
