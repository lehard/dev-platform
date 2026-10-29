## ADDED Requirements

### Requirement: The lifecycle preflight repairs own paths and refuses foreign paths

The shared-workspace condition of the lifecycle preflight SHALL audit the registered paths of the task (including Git metadata of its worktree) without modifying them. A finding on a path owned by the current OS account SHALL be repaired by the existing repair and reported as repaired with the path list. A finding on a path owned by another account SHALL be refused before any expensive operation with the owner and the exact repair command; it SHALL NOT be repaired or skipped. An audit that cannot run SHALL refuse.

#### Scenario: Own worktree metadata without setgid

- **GIVEN** the task worktree's Git metadata directory belongs to the current account and lacks the group setgid bit
- **WHEN** the preflight runs
- **THEN** the bit is set, the path is reported as repaired, and the command proceeds

#### Scenario: Another account's path

- **GIVEN** a registered path owned by a different account lacks the group contract
- **WHEN** the preflight runs
- **THEN** the command exits non-zero before any selected command starts
- **AND** the message names the path, its owner and the `chgrp`/`chmod` command
