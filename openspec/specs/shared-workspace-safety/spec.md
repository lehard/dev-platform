# shared-workspace-safety Specification

## Purpose
Define safeguards that let concurrent agents share a workspace without overwriting or claiming each other's state.

## Requirements

### Requirement: Shared-workspace enforcement is limited to registered platform ownership

The platform SHALL audit or repair only an explicit allowlist of platform-owned collaboration paths: the registered integration root, required Git common-directory metadata, lifecycle state/locks and task-worktree administration directories. It SHALL NOT infer ownership solely because a path is ignored or located below `.claude`.

#### Scenario: External machine-local symlink exists

- **GIVEN** a tool-managed symlink exists under `.claude` outside the registered platform allowlist
- **WHEN** platform doctor or shared-workspace audit runs
- **THEN** it does not follow, chmod, chown or fail because of that symlink
- **AND** it continues to audit the registered platform-owned paths

#### Scenario: Owned metadata has restrictive permissions

- **GIVEN** a registered Git or lifecycle metadata path lacks the required group mode
- **WHEN** a supported preflight or audit runs
- **THEN** it reports or safely repairs that exact owned path according to the existing shared-workspace contract
- **AND** it does not widen its traversal to foreign machine-local paths

### Requirement: Foreign transient cache state does not block another worktree

Project-rendered permission verification SHALL distinguish a foreign transient tool cache below `.claude` from a tracked or platform-owned path. It SHALL not fail a current worktree's validation solely because another worktree is actively writing such a cache.

#### Scenario: Another worktree writes a partial dependency cache

- **GIVEN** a foreign `node_modules.partial.*` cache below `.claude` is changing while a current worktree starts typecheck
- **WHEN** its group-write preflight runs
- **THEN** the cache does not cause a false permission failure
- **AND** a non-compliant tracked application file still produces the normal actionable result

### Requirement: Ordinary lifecycle verification does not rewrite stable Git configuration

Dev Platform SHALL verify stable shared-repository Git configuration during ordinary task completion without rewriting an already-correct value.

#### Scenario: Shared configuration is already correct

- **WHEN** two ordinary task-completion preflights inspect the same integration repository
- **THEN** neither preflight writes `.git/config`
- **AND** the tasks do not contend on `config.lock` because of platform verification

#### Scenario: Shared configuration requires repair

- **WHEN** the configured value is missing or incorrect
- **THEN** repair occurs only through the existing serialized integration boundary
- **AND** the repaired value is verified before lifecycle continuation

### Requirement: Ephemeral Git maintenance paths are audited without timing failures

Dev Platform SHALL distinguish a path that disappears during observation from a durable unsafe workspace finding.

#### Scenario: Temporary lock disappears during audit

- **WHEN** an ephemeral Git lock is removed between discovery and inspection
- **THEN** audit performs a bounded rescan
- **AND** does not report a persistent workspace failure solely for that disappearance

#### Scenario: Durable unsafe state remains

- **WHEN** a permission, symlink, ownership or foreign-state problem remains after re-observation
- **THEN** lifecycle continues to fail closed with actionable diagnostics

### Requirement: Platform-owned shared file writers verify their published output

A supported platform-owned writer targeting a registered shared-workspace path SHALL publish its own file with group read and write permissions and SHALL verify the published inode before reporting success. A cooperative shell umask alone SHALL NOT count as proof. New supported writer entrypoints SHALL carry regression evidence for restrictive creation modes. Verification or repair SHALL remain confined to that writer's declared output and SHALL NOT modify another agent's files.

#### Scenario: Report is published under a restrictive umask

- **GIVEN** a Process Health Review report is published through the supported report entrypoint
- **AND** the caller has a restrictive umask
- **WHEN** the report is published in the registered friction reports path
- **THEN** the published inode is group readable and writable before the command succeeds

#### Scenario: Writer produces a noncompliant file

- **GIVEN** a platform-owned writer creates its declared shared output with mode 0644
- **WHEN** the writer verifies the publication boundary
- **THEN** the operation fails before reporting success or repairs only that newly published output and verifies it
- **AND** no neighboring or foreign-owned file is changed

#### Scenario: External editor creates a report

- **GIVEN** an editor outside the supported writer creates a machine-local report
- **WHEN** the post-review shared-workspace check runs
- **THEN** any missing group write is reported before the review is considered complete
- **AND** only the file owner is instructed to repair it
