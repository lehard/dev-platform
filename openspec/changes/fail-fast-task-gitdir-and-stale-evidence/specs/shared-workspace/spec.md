## MODIFIED Requirements

### Requirement: The lifecycle preflight repairs own paths and refuses foreign paths

The shared-workspace condition of the lifecycle preflight SHALL audit the registered paths of the task (including Git metadata of its worktree) without modifying them, and SHALL evaluate local source admission with the same function and over the same path set that publication admission evaluates (the task's approved sources and its whole Git administration directory). A finding on a path owned by the current OS account SHALL be repaired by the existing repair and reported as repaired with the path list. A finding on a path owned by another account SHALL be refused before any expensive operation with the owner and the exact repair command; it SHALL NOT be repaired or skipped. An audit that cannot run SHALL refuse.

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

### Requirement: Task git-dir state is created under the shared contract

Every directory and file the platform creates below a task worktree's Git administration directory SHALL be created with the shared group, group read/write and, for directories, setgid, independent of the filesystem's setgid inheritance and the process umask. Task start SHALL create the quick-task evidence directory this way, and every selected-check evidence write SHALL publish its file and parent directory this way, so validation never leaves a path that publication admission refuses.

#### Scenario: Fresh task worktree

- **WHEN** a multi-agent task worktree is started
- **THEN** its quick-task evidence directory exists with the shared group and group rwx+setgid

#### Scenario: Evidence written under a non-inheriting parent

- **GIVEN** the evidence directory does not exist and the filesystem does not inherit setgid
- **WHEN** selected checks record evidence
- **THEN** the evidence directory has group rwx+setgid and the evidence file has group read/write
- **AND** local source admission over the task finds no violation
