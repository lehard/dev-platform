# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Reusable evidence projections are checked before semantic rediscovery

For workflows that opt into Project Evidence Snapshots, the platform SHALL perform deterministic freshness/invalidation preflight before invoking an agent to rebuild semantic project context.

#### Scenario: Projection inputs are unchanged
- **WHEN** every relevant source identity for a projection still matches
- **THEN** the fresh projection is reused
- **AND** no model call is required solely to rediscover the same project facts

#### Scenario: Only one projection dependency changes
- **WHEN** a bounded source change affects one projection and dependency metadata proves other projections unaffected
- **THEN** only the affected projection requires rebuilding

#### Scenario: Snapshot revision is stale
- **WHEN** the consumer cannot prove the snapshot/projection applicable to current repository evidence
- **THEN** it treats that projection as stale and refreshes or escalates before relying on it

### Requirement: Snapshots remain bounded derived state

Project Evidence Snapshots SHALL NOT create a backlog, lifecycle authority, or canonical architecture registry.

#### Scenario: Snapshot exists
- **WHEN** an agent later authors OpenSpec or performs another managed action
- **THEN** canonical repository sources retain their existing authority
- **AND** the snapshot is only evidence/cache input
