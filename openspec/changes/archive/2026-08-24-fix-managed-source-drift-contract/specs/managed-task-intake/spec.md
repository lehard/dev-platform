## MODIFIED Requirements

### Requirement: Managed packages carry bounded source-Issue revision evidence

Managed-task authoring SHALL capture machine-comparable source-Issue revision evidence such that deterministic platform-owned authoring receipt metadata does not cause an immediate newly authored task to appear drifted from itself. Real user edits to the source Issue title/body before materialization SHALL remain detectable and SHALL require explicit acknowledgement or supersession.

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

#### Scenario: Newly authored task starts without a user edit

- **GIVEN** a managed task is authored and the platform writes its deterministic authoring receipt
- **AND** the user does not change the Issue scope
- **WHEN** the exact task is started
- **THEN** source revision validation succeeds without an acknowledgement retry.

#### Scenario: User edits scope before start

- **GIVEN** a managed task was authored
- **AND** the user materially changes its title or body before materialization
- **WHEN** start validates source revision evidence
- **THEN** it fails closed and exposes the recorded/current evidence needed for an explicit decision.
