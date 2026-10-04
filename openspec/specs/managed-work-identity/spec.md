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
