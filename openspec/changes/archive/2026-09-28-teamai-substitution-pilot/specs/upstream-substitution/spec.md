# upstream-substitution Specification Delta

## ADDED Requirements

### Requirement: TeamAI substitution boundary is recorded

Dev Platform SHALL keep a committed TeamAI substitution decision record. The record SHALL identify the exact evaluated stable version and hold exactly one decision for each of these overlap areas:

- shared agent resources and their distribution;
- version-bound or on-demand skills and instructions;
- project and team learnings and recall;
- codebase knowledge or wiki;
- dashboard and session, usage and friction analytics;
- multi-project management, roles and namespaces;
- model profiles.

Until a separately delivered adoption change integrates an area, that area SHALL remain Dev Platform-owned. TeamAI SHALL NOT be a dependency of Dev Platform or of managed projects.

#### Scenario: Pilot completes without adoption

- **GIVEN** the TeamAI pilot recorded its decisions
- **WHEN** no adoption change has been delivered
- **THEN** every overlap area is Dev Platform-owned
- **AND** rendered managed projects neither install nor invoke TeamAI

#### Scenario: Area is decided adopt-next-step

- **GIVEN** an area is recorded as `adopt-next-step`
- **WHEN** the decision record is reviewed
- **THEN** it names the own implementation to retire and its measured size
- **AND** integration happens only through a separate change under the adoption requirement of this capability
