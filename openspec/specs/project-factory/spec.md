# Project Factory Specification

## Purpose

The Project Factory SHALL define the reusable, versioned contract for creating and safely updating agent-first repositories without taking ownership of application-domain behavior.

## Requirements

### Requirement: Central versioned project factory

The platform SHALL provide a central Copier-based factory for creating new agent-first repositories and delivering reviewed updates to existing managed repositories.

#### Scenario: New project creation

- **WHEN** a new repository is rendered from a stable platform release
- **THEN** it receives the selected workflow profile, shared agent rules, OpenSpec policy, local workflow scripts, check configuration and self-contained CI scaffolding

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

The platform SHALL define OpenSpec policy and compatibility expectations but SHALL NOT vendor OpenSpec-generated Claude/Codex skills as platform-owned source. Existing repositories SHALL adopt or update OpenSpec through reviewed actions rather than destructive blind initialization.

#### Scenario: OpenSpec integration is refreshed

- **WHEN** a repository needs updated OpenSpec-generated agent integrations
- **THEN** the external OpenSpec CLI generates them and the platform does not hand-maintain those generated skills

### Requirement: Updates are reviewed

Copier updates SHALL be applied as reviewable repository changes. The platform SHALL NOT remotely overwrite downstream project content or silently resolve update conflicts.

#### Scenario: Existing repository receives a platform update

- **WHEN** Copier produces changes or conflicts in a managed repository
- **THEN** the resulting diff is reviewed and unresolved conflicts block completion rather than being silently overwritten
