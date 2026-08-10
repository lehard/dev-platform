# Project Factory Specification

## Purpose

The Project Factory SHALL define the reusable, versioned contract for creating and safely updating agent-first repositories without taking ownership of application-domain behavior.
## Requirements
### Requirement: Central versioned project factory

The platform SHALL provide a central Copier-based factory for creating new agent-first repositories and delivering reviewed updates to existing managed repositories.

#### Scenario: New project creation

- **WHEN** a new repository is rendered from a stable platform release
- **THEN** it receives the selected workflow profile, shared agent rules, OpenSpec policy, local workflow scripts, check configuration and self-contained CI scaffolding

### Requirement: Human-facing onboarding is one operation

The platform SHALL expose one first-time onboarding operation that accepts a repository and chooses the safe adoption process from repository state rather than requiring the human to select workflow internals.

#### Scenario: Human starts onboarding

- **WHEN** the human supplies an eligible `owner/name` repository to the onboarding workflow
- **THEN** the platform selects fresh, existing or already-adopted handling without asking for Copier profile, harness mode, publish mode or OpenSpec bootstrap steps

### Requirement: Fresh repositories use a validated fast path

A repository SHALL be eligible for automatic fresh adoption only when it has no existing Dev Platform metadata, no known project-process markers and remains below conservative repository-size thresholds. Fresh adoption SHALL use platform-selected defaults, validate the rendered result, retain an auditable PR, and MAY auto-merge only after required validation passes.

#### Scenario: Nearly empty repository is onboarded

- **GIVEN** a repository has no process markers and is below fresh thresholds
- **WHEN** onboarding renders the exact stable platform release
- **THEN** it initializes the platform OpenSpec workflow set, runs platform/OpenSpec/project validation, merges the adoption PR automatically, and promotes the repository to `managed`

#### Scenario: Fresh validation fails

- **WHEN** Copier conflicts, platform doctor, OpenSpec validation or selected project checks fail
- **THEN** onboarding stops without merging the target default branch or promoting the repository to `managed`

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

### Requirement: Local readiness has one entrypoint

Generated repositories SHALL provide one idempotent developer readiness entrypoint that safely synchronizes the integration branch when applicable, restores configured OpenSpec agent integrations using the platform workflow set, and runs platform/agent health checks.

#### Scenario: Developer opens an adopted clone

- **WHEN** the developer or agent runs `python3 scripts/dev.py ready`
- **THEN** local readiness is established without requiring the human to remember separate sync, OpenSpec init/update, platform doctor and agent doctor commands

### Requirement: Project and platform ownership remain separate

The platform SHALL own reusable engineering process only. Application/domain rules and project-specific architecture SHALL remain project-owned and SHALL NOT be promoted into the shared template unless they are demonstrably reusable.

#### Scenario: Project-specific rule is encountered

- **WHEN** an application-specific invariant is needed by only one downstream repository
- **THEN** the rule remains in that repository instead of becoming a platform default

### Requirement: Runtime workflow is self-contained

Generated repositories SHALL contain the platform-managed scripts needed for normal agent workflow and SHALL NOT require runtime access to the central `dev-platform` repository.

#### Scenario: Downstream repository runs normal workflow

- **WHEN** an agent starts, validates or publishes work in a generated repository
- **THEN** the required platform workflow executes from files present in that repository

### Requirement: OpenSpec remains an external tool

The platform SHALL define OpenSpec policy and compatibility expectations but SHALL NOT vendor OpenSpec-generated Claude/Codex skills as platform-owned source. Automated initialization SHALL be limited to the fresh adoption path or an explicit local readiness action; arbitrary mature-repository migration SHALL remain reviewed.

#### Scenario: OpenSpec integration is refreshed locally

- **WHEN** an adopted repository needs its configured OpenSpec agent integrations restored or updated
- **THEN** the external OpenSpec CLI generates them using the platform-selected workflow profile without modifying the developer's persistent global OpenSpec profile

### Requirement: Ordinary updates are reviewed

Copier upgrades to already managed repositories SHALL be applied as reviewable repository changes. The platform SHALL NOT remotely overwrite downstream project content or silently resolve update conflicts.

#### Scenario: Existing managed repository receives a platform update

- **WHEN** Copier produces changes or conflicts in a managed repository
- **THEN** the resulting diff is reviewed and unresolved conflicts block completion rather than being silently overwritten

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

### Requirement: Project configuration records main protection and PR merge policy

Generated project configuration SHALL explicitly record whether the integration branch is expected to be protected and how ordinary task PRs are completed.

#### Scenario: Standard project is generated for protected delivery

- **WHEN** a standard or multi-agent platform-owned project is generated with normal safe defaults
- **THEN** configuration records `protected_main=true`, `publish_mode=pr`, and `pr_merge_mode=auto`

#### Scenario: Intentionally simple unprotected project uses direct publication

- **WHEN** a project deliberately uses direct publication
- **THEN** configuration records `protected_main=false`
- **AND** doctor can distinguish that choice from an accidental protected-main mismatch

### Requirement: Invalid protected-main publication combinations are rejected during configuration

The project factory SHALL reject or clearly fail validation for combinations that cannot satisfy the protected-main lifecycle.

#### Scenario: Protected light project requests direct publication

- **GIVEN** the light profile has no mandatory feature branch
- **WHEN** protected main is enabled with direct publication
- **THEN** generation/doctor rejects the combination
- **AND** instructs the project to use a feature-capable profile or a reviewed project-owned harness

### Requirement: Project-owned harness workflow guidance is preserved during upgrades

For `harness_mode=project`, Copier SHALL preserve an existing repository-owned `docs/engineering/agent-workflow.md` rather than replacing it with the generic platform harness guide.

#### Scenario: Mature project owns workflow guidance

- **GIVEN** `harness_mode=project`
- **AND** `docs/engineering/agent-workflow.md` already exists
- **WHEN** a reviewed Copier upgrade is applied
- **THEN** that file is preserved without conflict
- **AND** repository-specific publication and CI guidance remains authoritative

#### Scenario: Platform owns workflow guidance

- **GIVEN** `harness_mode=platform`
- **WHEN** a Copier upgrade changes generic workflow guidance
- **THEN** the platform-managed `docs/engineering/agent-workflow.md` remains eligible for update
