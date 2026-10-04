# managed-work-identity Specification

## Purpose
Keep human-readable Business Requirement identity stable across managed technical work while preserving canonical ownership and the private-lineage boundary.

## Requirements

### Requirement: Requirements and children have stable readable work identity
A Business Requirement SHALL have readable identity BR-N derived from its existing GitHub Issue number. Each linked technical child SHALL have one stable positive ordinal identity BR-N/Tn assigned automatically through the existing Requirement/child linkage, without a separate registry or status store. The private canonical parent reference SHALL remain intact. Repeated linking, retry, import and materialization SHALL preserve the same assignment. Conflicting or duplicate assignments SHALL fail closed. Removed or reordered child links SHALL NOT cause an assigned identity to be reused or renumbered. Legacy linked children SHALL be supported through normal lifecycle entrypoints without an unrelated manual migration.

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
New branches for linked managed children SHALL carry their validated readable BR-N/Tn identity in a branch-safe form. Existing task branches SHALL remain resumable without renaming or taking over another scope. Child PR titles SHALL include [BR-N/Tn] and a standard public-safe identity block. Shared Requirement PRs SHALL include [BR-N] and list all included child BR identities, updating the same draft PR as delivery grows. Normal lifecycle commands SHALL derive this automatically without a separate manual step, while preserving exact-head publication, GitHub protection and user-authored PR content. Unlinked technical and quick tasks SHALL remain supported. Public identity text SHALL contain only validated BR tokens and no private Backlog name/URL/reference or Requirement content.

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
