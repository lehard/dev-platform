## ADDED Requirements

### Requirement: Frontend design guidance is an opt-in capability

Dev Platform SHALL allow eligible projects or tasks to opt into agent-facing frontend design guidance without requiring that design context for unrelated work or imposing one aesthetic profile on all managed projects.

#### Scenario: UI design task opts in
- **WHEN** an eligible UI creation, substantial redesign or UI-quality task uses a configured design capability
- **THEN** the agent can load the selected general or specialized design guidance
- **AND** project-owned product/design requirements remain authoritative

#### Scenario: Unrelated task runs
- **WHEN** a backend, non-design or otherwise ineligible task executes
- **THEN** design capability context is not required solely because the project contains frontend code

### Requirement: Specialized visual profiles require explicit suitability

Specialized visual profiles SHALL NOT become universal defaults and SHALL be selected only when their declared visual purpose matches the project/task.

#### Scenario: High-end marketing profile exists
- **WHEN** a project uses a dashboard/B2B workflow without an explicit matching design choice
- **THEN** a high-end/marketing visual profile is not silently applied as the default

### Requirement: External design skills remain reviewable development tooling

Any external design skill integrated by Dev Platform SHALL use a pinned/provenance-tracked source or documented bounded adaptation and SHALL NOT independently change product intent, create managed work, or become a required production runtime dependency.

#### Scenario: External design skill is integrated
- **WHEN** Dev Platform integrates an external design skill or adapts its bounded principles
- **THEN** the integration records a pinned source revision or a documented bounded adaptation with source and license
- **AND** the skill does not change product intent, create managed backlog/spec work, or add a required production runtime dependency
