## ADDED Requirements

### Requirement: Existing-project adoption preserves proven project-owned harnesses

The platform SHALL treat repository state and harness ownership as separate adoption decisions. An existing repository that already owns a coherent Git/task/worktree/check lifecycle SHALL be adoptable with `harness_mode=project` without replacing that lifecycle with platform-owned implementations.

#### Scenario: Mature multi-agent repository is detected

- **GIVEN** an existing repository owns worktree coordination, agent-board state, merge/publish helpers and project-specific check selection
- **WHEN** first-time adoption is planned
- **THEN** the derived plan selects `harness_mode=project`
- **AND** selects `workflow_profile=multi-agent` when isolated worktrees and agent/scope coordination are both detected
- **AND** keeps `publish_mode=pr` for the reviewed existing-project migration

#### Scenario: Existing repository has no coherent project harness

- **GIVEN** an existing repository contains code or process markers but does not own a coherent lifecycle that would conflict with the platform harness
- **WHEN** first-time adoption is planned
- **THEN** the platform MAY retain `harness_mode=platform` using conservative compatible defaults

#### Scenario: Harness ownership is ambiguous

- **WHEN** adoption finds conflicting lifecycle paths but cannot safely determine ownership
- **THEN** it fails closed or leaves an explicit review blocker
- **AND** does not silently overwrite the existing lifecycle files

### Requirement: Adoption plan is auditable without exposing routine internals to the human

The normal onboarding interface SHALL continue to accept only the repository identifier while the adoption output records the derived repository kind, workflow profile, harness mode, publish mode and evidence for non-default ownership decisions.

#### Scenario: Human starts mature repository onboarding

- **WHEN** the human runs `Adopt Project` for an eligible mature repository
- **THEN** no routine workflow-profile or harness-mode question is required
- **AND** the workflow summary or adoption PR explains why project-owned harness behavior was selected

### Requirement: Mature migration validates platform health separately from product health

For `harness_mode=project`, first-time adoption SHALL validate platform/OpenSpec integration without requiring the repository-owned project check selector to implement the platform selector CLI contract. Product/application verification SHALL remain the responsibility of the repository-owned CI and engineering rules.

#### Scenario: Project selector uses a different CLI

- **GIVEN** an existing project has its own `scripts/select_checks.py` that does not support `--execute` or `--full`
- **WHEN** adoption prepares a `harness_mode=project` migration
- **THEN** platform preparation does not invoke those unsupported flags
- **AND** still validates platform metadata, conflict hygiene and OpenSpec lifecycle/structure

#### Scenario: Adoption PR enters project CI

- **WHEN** the reviewed mature-project adoption PR is opened
- **THEN** the repository's existing CI may run its application checks in the dependency environment it already owns
- **AND** the platform does not require duplicate pre-PR product execution to consider migration preparation successful

### Requirement: Existing-project path collisions preserve explicit ownership

First-time adoption SHALL treat existing path collisions as ownership decisions. Project-owned files SHALL be preserved, new platform-managed files SHALL be installed when non-colliding, and unresolved ownership ambiguity SHALL remain reviewable or blocking rather than being silently overwritten.

#### Scenario: Existing project owns lifecycle documentation

- **GIVEN** a mature repository already has project-specific engineering/OpenSpec guidance at a path that would otherwise collide with generic platform guidance
- **WHEN** adoption renders the platform
- **THEN** the existing guidance is not destructively replaced
- **AND** required platform guidance is installed through an explicit ownership-safe mechanism

## MODIFIED Requirements

### Requirement: Existing repositories use cautious reviewed migration

Repositories that already contain project process contracts or exceed fresh thresholds SHALL NOT use automatic merge. Existing project OpenSpec/tool state and proven project-owned lifecycle components SHALL NOT be destructively initialized or replaced during first-time migration. Adoption SHALL derive a safe harness/profile plan before rendering.

#### Scenario: Existing project is detected

- **WHEN** onboarding finds an existing agent/OpenSpec/CI process marker or repository-size threshold is exceeded
- **THEN** it derives repository kind and harness ownership separately
- **AND** creates a reviewable adoption PR
- **AND** stops before merge or managed promotion

#### Scenario: Existing adoption has been reviewed and merged

- **GIVEN** the project default branch now contains Dev Platform ownership metadata
- **WHEN** the same onboarding operation is run again
- **THEN** it skips recopy and performs the mechanical central `managed` promotion
