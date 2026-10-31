# managed-work-identity Specification

## Purpose
Keep human-readable Business Requirement identity stable across managed technical work while preserving canonical ownership and the private-lineage boundary.

## Requirements

### Requirement: Requirements and children have stable readable work identity

A Business Requirement SHALL have readable identity BR-N derived from its existing GitHub Issue number.

#### Scenario: Two children are linked and retried
- **WHEN** two technical children are linked to one Requirement and those link operations are retried
- **THEN** the children expose distinct BR-N/T1 and BR-N/T2 identities and the same parent BR-N
- **AND** retries and reordering preserve their assigned identities

#### Scenario: Conflicting child identity
- **WHEN** a child identity disagrees with its canonical parent or duplicates a sibling ordinal
- **THEN** linking/import fails with actionable diagnostics rather than silently changing ownership

### Requirement: Readable identity preserves native ownership and project taxonomy
Managed identity SHALL use native GitHub Assignee for responsibility and SHALL NOT require owner labels. Project-specific area and optional kind labels SHALL remain project-owned and SHALL NOT require a shared product taxonomy.

#### Scenario: Downstream project defines taxonomy
- **WHEN** a managed downstream project uses its own area labels and optional kind labels
- **THEN** BR identity works independently of those labels and without owner labels

### Requirement: Managed branches and PRs automatically expose readable identity

New branches for linked managed children SHALL carry their validated readable BR-N/Tn identity in a branch-safe form.

#### Scenario: Linked child starts and publishes
- **WHEN** a linked child is started and published through normal lifecycle entrypoints
- **THEN** its new branch and PR show its parent BR and child ordinal automatically
- **AND** its public objects contain no private Backlog references or contents

#### Scenario: Shared delivery grows
- **WHEN** a shared Requirement draft PR grows from one ready child to two ready children
- **THEN** the same PR title shows the parent BR and its identity block includes both distinct child IDs
- **AND** normal exact-head protected delivery remains required

#### Scenario: Legacy task resumes
- **WHEN** a task already has a registered branch from before BR naming was introduced
- **THEN** resume preserves that branch and automatically adds readable identity to its PR when canonical parent identity is provable

#### Scenario: Exact-head presentation retry
- **WHEN** a proven exact-head PR has an absent or stale BR prefix or standard identity block
- **THEN** publication repairs the same PR idempotently and preserves its user-authored title remainder and body outside that block
- **AND** canonical claims that conflict with committed provenance block remote publication

#### Scenario: Additive manifest identity
- **WHEN** a shared candidate carries readable parent and child identity metadata
- **THEN** opaque exact lineage and canonical manifest-path ownership remain authoritative
- **AND** old manifests and early candidates remain resumable as ordered exact prefixes without changing their registered branch or PR

#### Scenario: Project-owned helper predates branch identity
- **WHEN** a fresh linked child requires a new BR branch but its project-owned start helper cannot accept a branch name
- **THEN** intake stops before branch creation with an actionable compatibility error
- **AND** unlinked tasks and previously recorded legacy branches remain supported

### Requirement: Linked technical children receive an automatic ordinal identity

Each linked technical child SHALL have one stable positive ordinal identity BR-N/Tn assigned automatically through the existing Requirement/child linkage, without a separate registry or status store.

#### Scenario: Child is linked to a Requirement

- **WHEN** a technical child is linked to Requirement BR-N
- **THEN** it is assigned one stable positive ordinal identity BR-N/Tn automatically through the existing Requirement/child linkage
- **AND** no separate registry or status store is used

### Requirement: Readable identity keeps the private canonical parent reference

The private canonical parent reference SHALL remain intact.

#### Scenario: Readable identity is assigned

- **WHEN** a readable BR-N or BR-N/Tn identity is assigned
- **THEN** the private canonical parent reference remains intact

### Requirement: Repeated child operations preserve the identity assignment

Repeated linking, retry, import and materialization SHALL preserve the same assignment.

#### Scenario: Child link is repeated

- **WHEN** linking, retry, import or materialization of an assigned child is repeated
- **THEN** the child keeps the same assignment

### Requirement: Conflicting child identity assignments fail closed

Conflicting or duplicate assignments SHALL fail closed.

#### Scenario: Duplicate assignment

- **WHEN** a child identity assignment conflicts with or duplicates another assignment
- **THEN** the operation fails closed

### Requirement: Assigned child identities are never reused or renumbered

Removed or reordered child links SHALL NOT cause an assigned identity to be reused or renumbered.

#### Scenario: Child links are removed or reordered

- **WHEN** child links are removed or reordered
- **THEN** no assigned identity is reused or renumbered

### Requirement: Legacy linked children are supported without a manual migration

Legacy linked children SHALL be supported through normal lifecycle entrypoints without an unrelated manual migration.

#### Scenario: Legacy child enters the lifecycle

- **WHEN** a legacy linked child is handled through normal lifecycle entrypoints
- **THEN** it is supported without an unrelated manual migration

### Requirement: Existing task branches remain resumable without renaming

Existing task branches SHALL remain resumable without renaming or taking over another scope.

#### Scenario: Existing task branch resumes

- **WHEN** an existing task branch is resumed
- **THEN** it is resumable without renaming
- **AND** the resume does not take over another scope

### Requirement: Child PR titles carry the readable child identity

Child PR titles SHALL include [BR-N/Tn] and a standard public-safe identity block.

#### Scenario: Child PR is published

- **WHEN** a linked child PR is published
- **THEN** its title includes [BR-N/Tn]
- **AND** it includes a standard public-safe identity block

### Requirement: Shared Requirement PRs list all included child identities

Shared Requirement PRs SHALL include [BR-N] and list all included child BR identities, updating the same draft PR as delivery grows.

#### Scenario: Shared Requirement PR grows

- **WHEN** delivery of a shared Requirement PR grows
- **THEN** the PR includes [BR-N] and lists all included child BR identities
- **AND** the same draft PR is updated

### Requirement: Lifecycle commands derive readable branch and PR identity automatically

Normal lifecycle commands SHALL derive the readable branch and PR identity automatically without a separate manual step, while preserving exact-head publication, GitHub protection and user-authored PR content.

#### Scenario: Normal lifecycle command publishes

- **WHEN** a normal lifecycle command creates a branch or publishes a PR
- **THEN** it derives the readable identity automatically without a separate manual step
- **AND** exact-head publication, GitHub protection and user-authored PR content are preserved

### Requirement: Unlinked technical and quick tasks remain supported

Unlinked technical and quick tasks SHALL remain supported.

#### Scenario: Unlinked task runs

- **WHEN** an unlinked technical or quick task runs
- **THEN** it remains supported

### Requirement: Public identity text contains only validated BR tokens

Public identity text SHALL contain only validated BR tokens and no private Backlog name/URL/reference or Requirement content.

#### Scenario: Public identity text is rendered

- **WHEN** public identity text is rendered on a branch or PR
- **THEN** it contains only validated BR tokens
- **AND** it contains no private Backlog name/URL/reference or Requirement content
