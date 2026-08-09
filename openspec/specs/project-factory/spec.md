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

Repositories that already contain project process contracts or exceed fresh thresholds SHALL NOT use automatic merge. Existing project OpenSpec/tool state SHALL NOT be destructively initialized during first-time migration.

#### Scenario: Existing project is detected

- **WHEN** onboarding finds an existing agent/OpenSpec/CI process marker or repository-size threshold is exceeded
- **THEN** it creates a reviewable adoption PR and stops before merge or managed promotion

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
