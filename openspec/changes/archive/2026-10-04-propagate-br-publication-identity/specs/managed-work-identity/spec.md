## ADDED Requirements

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
