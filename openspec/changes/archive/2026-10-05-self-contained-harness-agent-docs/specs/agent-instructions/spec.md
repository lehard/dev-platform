# agent-instructions Specification Delta

## ADDED Requirements

### Requirement: Delivered documentation is navigable and self-contained for agents

A project rendered from the Dev Platform template SHALL include a documentation map reachable from its root `AGENTS.md` that states the roles of `AGENTS.md`, `docs/`, accepted OpenSpec specs, active OpenSpec changes and code and points to the canonical document for each concern. The delivered OpenSpec guidance SHALL describe the artifact roles, accepted specs versus active delta, requirements and scenarios, contract change during implementation, semantic verification, archive, and the boundary between upstream OpenSpec and Dev Platform entrypoints, so that the standard lifecycle can be completed without external OpenSpec documentation. Root `AGENTS.md` SHALL remain a bounded map.

#### Scenario: Agent looks for the right document

- **GIVEN** a freshly rendered project
- **WHEN** an agent follows the pointers from `AGENTS.md`
- **THEN** it reaches the docs map and from there the concern document, and every local link resolves

#### Scenario: Agent runs the OpenSpec lifecycle

- **WHEN** an agent reads the delivered OpenSpec guidance
- **THEN** it can identify each artifact's role and the Dev Platform entrypoints for start, verify and archive
- **AND** upstream OpenSpec documentation is described as supplementary, not required
