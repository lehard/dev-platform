## MODIFIED Requirements

### Requirement: Judgment evaluation separates deterministic ground truth from model judgment

For each judgment in the taxonomy, the pilot SHALL classify it as deterministic-checkable (established directly, for example by tests, file existence, exit status, exact version, or changed paths) or model-judged (a genuinely ambiguous semantic property).

#### Scenario: Deterministic judgment reuses existing evidence

- **GIVEN** a judgment can be established directly from test results, file existence, exit status, an exact version, or changed paths
- **WHEN** the pilot benchmark scores that judgment
- **THEN** the deterministic/rule result is treated as ground truth
- **AND** no model backend's output for that judgment is treated as authoritative

#### Scenario: No ground truth is invented

- **GIVEN** a replay case has no reliable independent reference for a judgment
- **WHEN** the benchmark records that judgment's outcome
- **THEN** it is recorded as `unknown/not-labelable`
- **AND** no backend's own output is substituted as ground truth

## ADDED Requirements

### Requirement: A deterministic-checkable judgment is not scored from model output

A deterministic-checkable judgment SHALL NOT be scored using any model backend's output as its source of truth.

#### Scenario: Deterministic-checkable judgment is scored

- **WHEN** the pilot scores a deterministic-checkable judgment
- **THEN** no model backend's output is used as its source of truth

### Requirement: Reference verdicts are recorded independently of the evaluated backend

Reference verdicts SHALL be recorded independently of the backend under evaluation.

#### Scenario: Reference verdict is recorded

- **WHEN** the pilot records a reference verdict
- **THEN** it is recorded independently of the backend under evaluation

### Requirement: An unlabelable judgment case is recorded as not labelable

An unlabelable case SHALL be recorded as `unknown/not-labelable` rather than a fabricated ground truth.

#### Scenario: Case cannot be labeled

- **WHEN** the pilot records an unlabelable case
- **THEN** it is recorded as `unknown/not-labelable`
- **AND** no fabricated ground truth is recorded for it
