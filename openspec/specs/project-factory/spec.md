# Project Factory

## Requirements

### Requirement: Central versioned project factory
The platform SHALL provide a central Copier-based factory for creating new agent-first repositories and delivering reviewed updates to existing managed repositories.

#### Scenario: new project creation
- **WHEN** a new repository is rendered from a stable platform release
- **THEN** it receives the selected workflow profile, shared agent rules, OpenSpec policy, local workflow scripts, check configuration and self-contained CI scaffolding

### Requirement: Project and platform ownership remain separate
The platform SHALL own reusable engineering process only. Application/domain rules and project-specific architecture SHALL remain project-owned and SHALL NOT be promoted into the shared template unless they are demonstrably reusable.

### Requirement: Runtime workflow is self-contained
Generated repositories SHALL contain the platform-managed scripts needed for normal agent workflow and SHALL NOT require runtime access to the central `dev-platform` repository.

### Requirement: OpenSpec remains an external tool
The platform SHALL define OpenSpec policy and compatibility expectations but SHALL NOT vendor OpenSpec-generated Claude/Codex skills as platform-owned source. Existing repositories SHALL adopt or update OpenSpec through reviewed actions rather than destructive blind initialization.

### Requirement: Updates are reviewed
Copier updates SHALL be applied as reviewable repository changes. The platform SHALL NOT remotely overwrite downstream project content or silently resolve update conflicts.
