# shared-workspace Specification

## Purpose
Operator-local, opt-in support for several local users sharing project sources, Git worktrees and platform state: bounded owner-only permission repair, hook composition that preserves existing hooks, an external registry with per-user automation, and read-only source admission in task lifecycle commands.

## Requirements

### Requirement: Opt-in local source permission policy
The platform SHALL support an operator-local policy for allowed application source paths, separate from platform-owned shared state. Repair SHALL change only current-user owned paths within reviewed roots and shared-group membership, SHALL avoid secrets, generated dependencies, symlinks and foreign active worktrees, and SHALL diagnose exact unrepairable paths. Opted-in lifecycle admission SHALL check allowed source paths before mutation.

#### Scenario: Restrictive or atomic source write
- **GIVEN** a registered checkout with an explicit source policy
- **WHEN** its owner creates or atomically replaces an allowed source file with restrictive group permissions
- **THEN** an owner audit restores group read/write and directory group traversal/write plus setgid
- **AND** a foreign-owner audit reports the path without changing it

#### Scenario: Foreign active task
- **WHEN** the policy runs inside another user's active worktree
- **THEN** it refuses to repair or launch task commands there

### Requirement: Preserve hook composition
Local attachment SHALL preserve existing hook arguments, stdin and failure status, including platform hooks refreshed by doctor. Attachment SHALL be idempotent and removable without deleting foreign hooks.

#### Scenario: Doctor refresh and failing hook
- **GIVEN** an attached checkout whose original pre-commit hook is refreshed
- **WHEN** the refreshed hook rejects a commit
- **THEN** the composed hook invokes that refreshed hook and returns failure

### Requirement: Automatically attach registered local projects
A reviewed external registry SHALL drive identity-scoped discovery, versioned runtime installation and updates across local projects. Automatic per-user sync SHALL operate only in reviewed workspace roots, SHALL preserve existing configuration, and SHALL report unavailable projects or foreign-owner drift. A cooperative launcher SHALL set umask 0002 and audit allowed source paths before and after commands. Mac-specific paths and users SHALL stay in operator-local configuration.

#### Scenario: New registered project
- **GIVEN** a reviewed workspace root and project repository inventory
- **WHEN** a matching integration checkout appears and sync runs
- **THEN** it receives the current local policy and composed hooks automatically
- **AND** an unrelated checkout remains unchanged

#### Scenario: Both user identities
- **WHEN** either permitted group member runs the installed automation
- **THEN** their own allowed newly created files and worktree metadata are repaired
- **AND** the other user's active worktree remains untouched

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
