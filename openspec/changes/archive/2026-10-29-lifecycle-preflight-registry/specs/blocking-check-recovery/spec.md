## ADDED Requirements

### Requirement: Every blocking gate is registered with a preflight condition or a justification

Each entry of the blocking-gate catalog SHALL carry exactly one of `preflight`, naming a condition in the lifecycle preflight registry that checks the gate's condition ahead of expensive work, or `no_preflight`, a non-empty written reason why the condition cannot be checked ahead (for example, it depends on the result of the tests themselves). Catalog validation SHALL fail explicitly for an entry with neither or both, and a test SHALL fail when a `preflight` id is not a registered condition, when a registered condition names a gate that does not reference it, or when a `no_preflight` reason is empty.

#### Scenario: Gate added without a decision

- **WHEN** a catalog entry has neither `preflight` nor `no_preflight`
- **THEN** loading the catalog fails naming the gate

#### Scenario: Unknown condition

- **WHEN** a catalog entry names a `preflight` id absent from the registry
- **THEN** the registry test fails naming the gate and the id

#### Scenario: Justified absence

- **WHEN** a gate depends on the outcome of the run it would precede
- **THEN** its entry records `no_preflight` with that reason and the test passes
