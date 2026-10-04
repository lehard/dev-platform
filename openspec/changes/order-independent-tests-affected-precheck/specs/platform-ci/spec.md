## ADDED Requirements

### Requirement: Test groups are independent of module order and substitution

Platform test modules SHALL register platform modules in `sys.modules` only through one shared loader that reuses the instance already registered for the same file, and SHALL scope any temporary stand-in with patching that restores `sys.modules`, so that code under test and every test in a process share one instance per registered module name. A test MAY load a file under a distinct private alias name that production code never imports. A selected canonical test group SHALL produce the same result when run in isolation and inside its group. The platform SHALL include an automated guard that fails when a test registers a platform module outside the shared loader, or when, after importing test modules in forward or reverse order, a test holds a platform module that differs from the registered instance of the same name.

#### Scenario: Group runs in isolation and in its group
- **GIVEN** a canonical test group containing modules that previously replaced platform modules at import time
- **WHEN** the group runs alone and as part of its configured group order
- **THEN** both runs produce the same result

#### Scenario: A test substitutes a module instance
- **WHEN** a test module assigns a platform module into `sys.modules` directly, or holds an instance different from the registered one
- **THEN** the guard fails naming the test module and the module

### Requirement: Full-suite timing decisions are evidence-based

The platform SHALL record per-group wall-clock evidence for the full validation set and SHALL accept a structural speed change only with comparable before/after evidence and identical mandatory coverage; a no-change decision SHALL also be recorded with its data.

#### Scenario: Slowest group is split
- **WHEN** a split or rebalance of a slow group is proposed
- **THEN** coverage verification is identical before and after
- **AND** the comparable wall-clock evidence shows a reduction or the change is not adopted
