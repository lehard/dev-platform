## MODIFIED Requirements

### Requirement: Blocking checks declare a failure class

Every blocking platform check that reports through the shared helper SHALL be cataloged with a failure class of platform defect, supported recovery or justified hard stop.

#### Scenario: Uncataloged blocking check

- **GIVEN** a check blocks work through the shared helper with an id absent from the catalog
- **WHEN** it fires or platform validation runs
- **THEN** it fails explicitly naming the missing id.

### Requirement: Every blocking gate is registered with a preflight condition or a justification

Each entry of the blocking-gate catalog SHALL carry exactly one of `preflight`, naming a condition in the lifecycle preflight registry that checks the gate's condition ahead of expensive work, or `no_preflight`, a non-empty written reason why the condition cannot be checked ahead (for example, it depends on the result of the tests themselves).

#### Scenario: Gate added without a decision

- **WHEN** a catalog entry has neither `preflight` nor `no_preflight`
- **THEN** loading the catalog fails naming the gate

#### Scenario: Unknown condition

- **WHEN** a catalog entry names a `preflight` id absent from the registry
- **THEN** the registry test fails naming the gate and the id

#### Scenario: Justified absence

- **WHEN** a gate depends on the outcome of the run it would precede
- **THEN** its entry records `no_preflight` with that reason and the test passes

## ADDED Requirements

### Requirement: The failure-class catalog inventories the named blocking checks

The failure-class catalog of blocking checks SHALL inventory at least the blocking checks named by the Requirement.

#### Scenario: Catalog is inspected

- **WHEN** the blocking-check failure-class catalog is inspected
- **THEN** it inventories at least the blocking checks named by the Requirement

### Requirement: Catalog entries carry a recovery step or a justification

A recoverable entry of the failure-class catalog SHALL name a recorded recovery step; a hard-stop entry of that catalog SHALL carry a written justification.

#### Scenario: Catalog entry is classified

- **WHEN** a catalog entry is recoverable or a hard stop
- **THEN** a recoverable entry names a recorded recovery step
- **AND** a hard-stop entry carries a written justification

### Requirement: Uncataloged helper-reported blocking checks fail platform validation

A blocking check that reports through the helper without a catalog entry SHALL fail platform validation.

#### Scenario: Helper-reported check lacks an entry

- **WHEN** a blocking check reports through the helper without a catalog entry
- **THEN** platform validation fails

### Requirement: New or changed blocking checks are cataloged under review enforcement

A new or changed blocking check SHALL be added to the catalog and fail through the helper; this obligation is enforced by review, and the completeness of the inventory beyond the named checks is reported in the catalog and not asserted by validation.

#### Scenario: Blocking check is added or changed

- **WHEN** a blocking check is added or changed
- **THEN** it is added to the catalog and fails through the helper, which review enforces
- **AND** the completeness of the inventory beyond the named checks is reported in the catalog and not asserted by validation

### Requirement: Catalog validation rejects entries with neither or both preflight fields

Catalog validation SHALL fail explicitly for a blocking-gate catalog entry with neither or both of `preflight` and `no_preflight`.

#### Scenario: Entry has neither or both

- **WHEN** a blocking-gate catalog entry carries neither or both of `preflight` and `no_preflight`
- **THEN** catalog validation fails explicitly

### Requirement: A test rejects inconsistent preflight registrations

A test SHALL fail when a `preflight` id is not a registered condition, when a registered condition names a gate that does not reference it, or when a `no_preflight` reason is empty.

#### Scenario: Preflight registration is inconsistent

- **WHEN** a `preflight` id is not a registered condition, a registered condition names a gate that does not reference it, or a `no_preflight` reason is empty
- **THEN** a test fails
