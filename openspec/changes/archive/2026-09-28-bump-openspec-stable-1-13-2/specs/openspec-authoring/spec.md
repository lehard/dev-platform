# openspec-authoring Specification Delta

## MODIFIED Requirements

### Requirement: OpenSpec stable-version upgrades preserve lifecycle correctness

Dev Platform SHALL update its supported OpenSpec compatibility baseline only after the selected stable release passes representative managed lifecycle checks and focused regressions for correctness-sensitive upstream changes. Every recorded copy of the tested OpenSpec version -- the rendered `[tools.openspec]` configuration, every platform or rendered workflow that installs or invokes the OpenSpec CLI, and the tested-version documentation -- SHALL move together, and the focused regressions for an adopted release's correctness fixes SHALL remain in the exact-CLI regression suite that platform CI runs against the pinned version.

#### Scenario: Stable OpenSpec upgrade passes compatibility checks
- **WHEN** a newer stable OpenSpec release is selected for adoption
- **AND** representative materialize, validate, semantic verify and archive checks pass
- **AND** focused regressions for the motivating upstream correctness changes pass
- **THEN** the platform MAY update its minimum/tested OpenSpec version contract and matching fixtures/docs consistently
- **AND** SHALL retain platform semantic verification and lifecycle evidence unless a separate reviewed change proves a guard redundant

#### Scenario: Compatibility check finds a material regression
- **WHEN** the selected stable OpenSpec release violates a Dev Platform lifecycle invariant or fails a representative regression
- **THEN** the platform SHALL keep the existing supported contract
- **AND** SHALL record the incompatibility instead of weakening verification, archive, or source-of-truth guarantees merely to complete the dependency bump

#### Scenario: Adopted release fixes are pinned by behavior
- **GIVEN** a stable OpenSpec release is adopted because it fixes archive, validation, task-progress or verification correctness
- **WHEN** platform CI runs the exact-CLI regression suite against the pinned version
- **THEN** each motivating fix is exercised by a fixture that would fail against the previously tested version
- **AND** no recorded copy of the previous tested version remains in the platform or rendered template
