## ADDED Requirements

### Requirement: Test groups are independent of module order and substitution

Platform test modules SHALL NOT leave substituted platform modules in `sys.modules` beyond the scope of the test that needs them, so that code under test and the test share one module instance. A selected canonical test group SHALL produce the same result when run in isolation and inside its group. The platform SHALL include an automated guard that fails when a test leaks a substituted platform module.

#### Scenario: Group runs in isolation and in its group
- **GIVEN** a canonical test group containing modules that previously replaced platform modules at import time
- **WHEN** the group runs alone and as part of its configured group order
- **THEN** both runs produce the same result

#### Scenario: A test leaks a substituted module
- **WHEN** a test module leaves a substituted platform module in `sys.modules` after it finishes
- **THEN** the guard fails with the module name and the leaking test module

### Requirement: Full-suite timing decisions are evidence-based

The platform SHALL record per-group wall-clock evidence for the full validation set and SHALL accept a structural speed change only with comparable before/after evidence and identical mandatory coverage; a no-change decision SHALL also be recorded with its data.

#### Scenario: Slowest group is split
- **WHEN** a split or rebalance of a slow group is proposed
- **THEN** coverage verification is identical before and after
- **AND** the comparable wall-clock evidence shows a reduction or the change is not adopted
