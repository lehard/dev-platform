# platform-lifecycle Specification Delta

## ADDED Requirements

### Requirement: Corrected shared merge candidates preserve immutable generations

When a verified Requirement child chain changes after an earlier shared merge candidate fails required checks, the merge recovery lifecycle SHALL assign a distinct candidate generation using both the authoritative base and exact final child head. It SHALL preserve prior branches, worktrees and PR evidence, and SHALL still reject an occupied identical generation.

#### Scenario: New verified child at the same main base

- **GIVEN** a failed shared candidate at a main base and a corrected final child head
- **WHEN** the corrected chain is assembled
- **THEN** it receives a different branch, worktree and committed manifest identity
- **AND** the earlier generation remains untouched

#### Scenario: Identical chain is retried

- **GIVEN** a candidate already exists for the same exact base and final child head
- **WHEN** another preparation is attempted
- **THEN** the occupied-generation guard blocks duplication rather than overwriting it
