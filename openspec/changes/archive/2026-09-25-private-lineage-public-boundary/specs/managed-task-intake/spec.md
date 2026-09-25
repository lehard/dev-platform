# managed-task-intake Specification Delta

## ADDED Requirements

### Requirement: Public managed provenance uses opaque private lineage

A managed task sourced from a private Backlog Issue SHALL keep the exact Issue reference in the existing private Issue and ignored local task state. Publicly committed active and archived OpenSpec provenance and derived validation/integration receipts SHALL carry an opaque, non-derivable lineage handle instead of a private repository name or Issue number. The handle mapping SHALL live in that same private Issue; no second storage service is added. Missing or conflicting mapping SHALL block archive or publication.

#### Scenario: Private managed task is published

- **GIVEN** a managed task came from a private Backlog Issue
- **WHEN** its OpenSpec archive and verification evidence are committed
- **THEN** the public records contain only its opaque lineage handle
- **AND** an authorized private Issue read can prove that handle belongs to the exact task

#### Scenario: Resume from private Issue

- **WHEN** a previously published private managed task is resumed by its exact private Issue
- **THEN** the lifecycle fetches its handle through authorized private access and accepts only the matching canonical change
- **AND** absent or ambiguous mappings fail closed

#### Scenario: Existing public archive is migrated

- **GIVEN** a completed public archive contains the old exact private Issue reference
- **WHEN** its current-tree record is sanitized
- **THEN** past check outcomes and semantic verification remain truthful
- **AND** the post-verification redaction is explicitly identified without claiming historical Git removal

#### Scenario: Shared Requirement candidate is published

- **GIVEN** verified child receipts are assembled for a private Requirement
- **WHEN** the combined candidate is committed and published
- **THEN** its public branch, commit messages, manifest, PR text and process-evidence comments use opaque handles
- **AND** the exact private manifest is checked through authorized private mapping before publication
