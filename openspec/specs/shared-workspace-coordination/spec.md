# shared-workspace-coordination Specification

## Purpose
Fail managed intake closed before it mutates shared state whenever the live agent session or a pre-existing path cannot safely satisfy the shared-workspace group/permission contract.
## Requirements
### Requirement: Managed intake proves the live agent session can safely create shared artifacts

Before any supported managed intake path creates or reuses a task worktree,
materializes a managed OpenSpec package, or changes a Development Backlog
Project item, the platform SHALL run a disposable self-test of the live
execution under the shared-workspace root. The self-test SHALL prove effective
membership in the required shared group and actual creation of a group-writable
file, a group-writable setgid directory and an atomically replaced file that
each satisfy the shared-workspace contract. The test SHALL remove only its
uniquely created probe directory.

#### Scenario: A Codex or Claude session lacks the required creation behavior

- **WHEN** the session self-test cannot create or publish a required conforming
  probe artifact
- **THEN** intake fails without creating a task worktree or branch,
  materializing package files, or changing Project state
- **AND THEN** the diagnostic identifies the session-level fact that failed and
  tells the user to correct the launcher/session and restart or re-login only
  when that can address the failure

### Requirement: Managed intake refuses permission-drifted shared workspaces before mutation

Before any supported managed intake path creates or reuses a task worktree,
materializes a managed OpenSpec package, or changes a Development Backlog
Project item, the platform SHALL perform a read-only shared-workspace admission
audit at the integration root. If the bounded relevant audit set contains a
permission finding, intake SHALL fail before each of those mutations.

#### Scenario: Foreign-owned registered metadata is not writable by the current operator

- **WHEN** the admission audit finds one or more relevant shared paths that
  lack the required group/mode contract and cannot be repaired by the current
  operator
- **THEN** intake fails without creating a task worktree or branch,
  materializing package files, or changing Project state
- **AND THEN** the diagnostic lists every finding with path, owner, group/mode
  facts and one owner-specific remediation command

#### Scenario: Shared-workspace audit is clean

- **WHEN** the admission audit has no relevant permission findings
- **THEN** managed intake continues through its existing worktree,
  materialization and Project-state flow

### Requirement: Platform writers do not publish permission-drifted shared artifacts

Platform-owned shared-workspace writers, including the bounded Git worktree
creation boundary, SHALL create or verify published paths against the shared
group, group-write and directory setgid contract before allowing the next
managed lifecycle mutation.

#### Scenario: A writer starts under a restrictive creation mask

- **WHEN** a platform writer or worktree creation operation runs with a
  restrictive inherited creation mask
- **THEN** its published shared artifact satisfies the shared-workspace
  contract before subsequent task materialization proceeds

#### Scenario: Disposable single-user checkout is not a shared-workspace false positive

- **WHEN** managed intake runs in a valid disposable or CI checkout that the
  shared-workspace applicability rules classify as non-shared
- **THEN** the admission gate does not reject the checkout solely for missing
  shared group permissions

