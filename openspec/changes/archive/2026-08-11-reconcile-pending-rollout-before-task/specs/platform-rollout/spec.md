## ADDED Requirements

### Requirement: Pending rollout identity is reusable by downstream task preflight

The platform SHALL expose one structured eligibility contract for determining whether an open downstream PR is a platform-owned rollout. Central rollout automation and downstream pre-task reconciliation SHALL use the same ownership semantics based on configured repository/base, reserved rollout branch/version contract, and expected automation identity. PR title or body text SHALL NOT establish ownership.

#### Scenario: Pre-task reconciliation sees an old and a new rollout PR

- **GIVEN** multiple historical rollout records exist for the repository
- **WHEN** pre-task reconciliation chooses a candidate for automatic adoption
- **THEN** only the newest authoritative eligible pending rollout may be selected
- **AND** an older superseded rollout is not merged

#### Scenario: Similar-looking PR is not owned by rollout automation

- **WHEN** an open PR has a rollout-like title or body but does not satisfy the structured branch/base/automation identity contract
- **THEN** pre-task reconciliation does not treat it as an automatically adoptable platform rollout

### Requirement: Automatic release rollout remains reviewable

The release workflow SHALL continue to dispatch managed rollout automatically after publishing an immutable platform version, and ordinary rollout SHALL continue to stop at a reviewable downstream PR. Pre-task rollout reconciliation MAY later adopt that PR through normal downstream GitHub gates, but SHALL NOT redefine routine rollout creation as unconditional auto-merge.

#### Scenario: New immutable platform release is published

- **WHEN** release automation publishes `vX.Y.Z`
- **THEN** it dispatches managed rollout for that exact release
- **AND** a clean downstream update is opened as a reviewable rollout PR
- **AND** central rollout does not unconditionally merge that PR

### Requirement: Routine rollout delivery does not create managed backlog work

A routine platform rollout PR SHALL remain operational delivery state and SHALL NOT create a Development Backlog managed task solely because it is waiting for downstream adoption.

#### Scenario: Rollout PR waits for later adoption

- **WHEN** a clean rollout PR remains open after central rollout completes
- **THEN** no Development Backlog issue is created solely for that pending PR
- **AND** later supported task preflight is responsible for detecting and reconciling it
