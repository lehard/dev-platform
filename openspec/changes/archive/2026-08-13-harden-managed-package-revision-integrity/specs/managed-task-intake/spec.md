## ADDED Requirements

### Requirement: Authoring validates against the exact prepared target revision

Managed-task authoring SHALL validate a package against the same target repository revision that it records as `prepared_against`. A freshly fetched remote revision SHALL NOT be recorded as preparation evidence while semantic/structural validation is actually performed against a different stale local spec state.

#### Scenario: Local authoring checkout is stale

- **GIVEN** target `origin/main` has advanced beyond the local authoring checkout
- **WHEN** authoring prepares a package against the fetched remote revision
- **THEN** validation observes the exact fetched target state or authoring fails closed before publication
- **AND** the package is not represented as validated against a state it did not inspect

#### Scenario: Exact target state cannot be established

- **WHEN** authoring cannot safely establish the repository/spec state for the recorded `prepared_against` revision
- **THEN** no Issue/package publication occurs
- **AND** the diagnostic explains the synchronization or validation blocker

### Requirement: Managed packages carry bounded source-Issue revision evidence

Newly authored managed packages SHALL retain bounded machine-comparable evidence of the source Development Backlog Issue revision used during authoring. The evidence SHALL be sufficient to detect a later meaningful Issue edit without storing a second full canonical implementation plan.

#### Scenario: Source Issue changes before materialization

- **GIVEN** a package was authored from source Issue revision A
- **AND** the source Issue is materially edited to revision B before implementation starts
- **WHEN** managed start/import evaluates the task
- **THEN** the drift is reported before implementation
- **AND** the executor must explicitly reconcile/supersede the package or acknowledge that revision A remains the intended scope
- **AND** the old package is not silently treated as current human intent

#### Scenario: Source Issue changes after materialization

- **GIVEN** a package has already been materialized into canonical repository-local OpenSpec
- **WHEN** the human-facing Issue is edited later
- **THEN** lifecycle status can expose bounded drift evidence
- **AND** repository-local OpenSpec is not automatically overwritten or broadened

### Requirement: Published managed package revisions can be superseded safely before execution

The platform SHALL provide one supported idempotent operation to replace a published managed package revision when the transport is invalid or accepted pre-execution planning has been revised. The replacement SHALL be fully validated before becoming active, SHALL preserve bounded predecessor revision evidence, and SHALL leave exactly one active package revision for deterministic import.

#### Scenario: Invalid published package is repaired

- **GIVEN** the current package cannot pass supported intake validation
- **WHEN** an operator supplies a corrected authoring bundle through the supported repair/supersede path
- **THEN** the replacement is validated against current exact target state before activation
- **AND** the old revision is marked superseded by bounded revision evidence
- **AND** the importer resolves exactly one active revision without hand-editing GitHub content

#### Scenario: Supersede is retried with identical content

- **GIVEN** the requested replacement revision is already active
- **WHEN** the same supersede operation is retried
- **THEN** it converges as a no-op
- **AND** no duplicate active package is created

#### Scenario: Package revision history is ambiguous

- **WHEN** intake observes more than one active package revision or malformed supersession metadata
- **THEN** import fails closed before materialization
- **AND** reports the revision ambiguity rather than guessing
