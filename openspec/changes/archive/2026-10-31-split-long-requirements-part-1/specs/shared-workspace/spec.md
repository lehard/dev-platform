## MODIFIED Requirements

### Requirement: The lifecycle preflight repairs own paths and refuses foreign paths

A finding on a path owned by the current OS account SHALL be repaired by the existing repair and reported as repaired with the path list.

#### Scenario: Own worktree metadata without setgid

- **GIVEN** the task worktree's Git metadata directory belongs to the current account and lacks the group setgid bit
- **WHEN** the preflight runs
- **THEN** the bit is set, the path is reported as repaired, and the command proceeds

#### Scenario: Another account's path

- **GIVEN** a registered path owned by a different account lacks the group contract
- **WHEN** the preflight runs
- **THEN** the command exits non-zero before any selected command starts
- **AND** the message names the path, its owner and the `chgrp`/`chmod` command

#### Scenario: Own admission finding under the task git dir

- **GIVEN** local source admission is enabled and a directory below the task's Git administration directory belongs to the current account and lacks group rwx+setgid
- **WHEN** the preflight runs
- **THEN** the directory is repaired and reported as repaired
- **AND** publication admission later finds no violation on it

## ADDED Requirements

### Requirement: The lifecycle preflight audits registered task paths without modifying them

The shared-workspace condition of the lifecycle preflight SHALL audit the registered paths of the task (including Git metadata of its worktree) without modifying them.

#### Scenario: Registered task paths are audited

- **WHEN** the shared-workspace condition of the lifecycle preflight runs
- **THEN** it audits the registered paths of the task, including Git metadata of its worktree
- **AND** the audit itself does not modify those paths

### Requirement: The lifecycle preflight evaluates local source admission like publication admission

The shared-workspace condition of the lifecycle preflight SHALL evaluate local source admission with the same function and over the same path set that publication admission evaluates (the task's approved sources and its whole Git administration directory).

#### Scenario: Local source admission matches publication admission

- **WHEN** the shared-workspace condition of the lifecycle preflight evaluates local source admission
- **THEN** it uses the same function that publication admission evaluates
- **AND** it evaluates the same path set: the task's approved sources and its whole Git administration directory

### Requirement: The lifecycle preflight refuses a finding on another account's path

A finding on a path owned by another account SHALL be refused before any expensive operation with the owner and the exact repair command; it SHALL NOT be repaired or skipped.

#### Scenario: Finding on a foreign path

- **GIVEN** a finding on a path owned by another account
- **WHEN** the lifecycle preflight runs
- **THEN** the finding is refused before any expensive operation with the owner and the exact repair command
- **AND** the path is neither repaired nor skipped

### Requirement: The lifecycle preflight refuses when its shared-workspace audit cannot run

A shared-workspace audit of the lifecycle preflight that cannot run SHALL refuse.

#### Scenario: Audit cannot run

- **WHEN** the shared-workspace audit of the lifecycle preflight cannot run
- **THEN** the preflight refuses
