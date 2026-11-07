## ADDED Requirements

### Requirement: A later finish consumes earlier deferred cleanup records

A `finish` that completes terminal reconciliation SHALL process the deferred worktree records of earlier tasks, excluding its own, through the existing safety and identity checks, and SHALL name each removed worktree and each kept record with its reason.

#### Scenario: A later finish consumes earlier records

- **GIVEN** deferred records of earlier tasks exist
- **WHEN** a later `finish` completes its terminal reconciliation
- **THEN** each record passing the safety and identity checks is removed and named
- **AND** each other record is kept and named with its reason and exact command
- **AND** the record of the running task is kept and ordinary non-deferred candidates are untouched
- **AND** a failure of this cleanup is a warning and does not change the delivery result
