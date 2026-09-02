## ADDED Requirements

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
