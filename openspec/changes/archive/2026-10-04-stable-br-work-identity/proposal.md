## Why
Managed work currently has canonical parent links but no stable human-readable identity across its child objects. A parent-derived BR identifier makes that relationship visible while preserving private Backlog data.

## What Changes
- Derive BR-N from the existing parent Requirement and allocate BR-N/Tn using the existing parent/child relationship, with idempotent conflict-safe allocation.
- Automatically expose the identity in Requirement/child Issues and imported public-safe provenance.
- Permit only these readable identifiers publicly while preserving opaque technical provenance and forbidding private Backlog references or Requirement content.
- Keep native GitHub Assignee and project-owned optional area/kind taxonomy.

## Capabilities
### New Capabilities
- `managed-work-identity`: stable Requirement and technical-child presentation identity.
### Modified Capabilities
- `managed-task-intake`: public privacy boundary permits readable BR identifiers.

## Impact
Managed intake/linking/materialization and shared public provenance; existing Issues and packages remain importable. No separate registry or status store.

## Outcome and Evidence
A parent with two children yields distinct stable BR-N/T1 and BR-N/T2 on link, retry and import; conflicting identities fail closed; public provenance contains no private Backlog identity/content. Meaningful integration tests cover interruption recovery and legacy links. Release and downstream rollout follow joint delivery of this change and the dependent publication change.

## Non-goals
Branch/PR formatting is the dependent change. No GitHub number synchronization, owner labels or platform-wide product taxonomy.
