# shared-workspace-safety Specification

## Purpose
TBD - created by archiving change bound-shared-workspace-metadata. Update Purpose after archive.
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

