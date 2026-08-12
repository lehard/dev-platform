# goal-definition Specification

## Purpose
TBD - created by archiving change adopt-define-goal-intake. Update Purpose after archive.
## Requirements
### Requirement: Goal definition is selective and outcome-oriented

The platform SHALL support a transient goal-definition refinement step before OpenSpec/managed authoring when the user's request is materially fuzzy about the desired outcome or success evidence, or when the user explicitly requests goal-backed work. It SHALL NOT require this step for an ordinary concrete quick or implementation task.

A refined goal SHALL identify the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold, material scope bounds, and a condition that requires clarification rather than unbounded autonomous work.

#### Scenario: Fuzzy non-trivial request benefits from refinement

- **GIVEN** a non-trivial request whose intended result or validator is materially underspecified
- **WHEN** the platform prepares the request for planning or managed authoring
- **THEN** it first sharpens the request into a goal meeting the defined quality bar
- **AND** missing information that could change the intended result causes a concise clarification instead of invented requirements

#### Scenario: Concrete quick task does not need a goal

- **GIVEN** a small concrete request with an obvious completion condition
- **WHEN** normal task intake classifies it as quick execution
- **THEN** the existing quick-task lifecycle remains available without mandatory goal creation

### Requirement: Goal definition does not become a competing source of truth

The goal-definition step SHALL remain transient intake/refinement state. It SHALL NOT create a second backlog, durable snapshot, decision log, resume file or competing implementation plan. For a managed task, the Development Backlog Issue remains the human-facing task and the materialized repository-local OpenSpec remains the canonical implementation contract.

#### Scenario: Refined goal proceeds into managed authoring

- **GIVEN** a refined goal that the user explicitly asks to fix in the Development Backlog
- **WHEN** the managed Issue and OpenSpec package are authored
- **THEN** the goal informs the outcome and acceptance evidence in those artifacts
- **AND** no separate durable goal artifact competes with the Issue or OpenSpec after materialization

### Requirement: Official goal semantics are adopted without false runtime claims

The platform SHALL align its goal quality semantics with the official OpenAI `define-goal` quality contract and use the supported native goal capability (`/goal` or runtime-native goal tools) for explicit goal-backed requests when the agent runtime exposes it. Materially fuzzy intake that the user did not ask to make goal-backed SHALL remain a transient refinement rather than implicitly creating durable native goal state. The reusable integration SHALL use the platform's normal template/Copier distribution path and SHALL NOT claim successful goal-tool state when the runtime does not provide the required goal capability.

When the official goal capability is unavailable, the platform MAY fall back to an equivalent transient natural-language goal refinement that meets the same quality bar, or SHALL report the capability limitation explicitly.

#### Scenario: Supported goal runtime is available

- **GIVEN** the current supported Codex environment exposes the official goal capability
- **WHEN** goal-backed intake is requested
- **THEN** the platform uses the supported capability according to its official contract
- **AND** does not vendor an unnecessary competing implementation of the external skill

#### Scenario: Goal runtime is unavailable

- **GIVEN** the current agent environment cannot create or inspect official goal state
- **WHEN** goal refinement is needed
- **THEN** the workflow either performs an explicitly transient equivalent refinement or reports the limitation
- **AND** it does not fabricate `create_goal`/active-goal success

### Requirement: Goal definition is independent of model-specific critic orchestration

Goal refinement SHALL NOT require a Sol-to-Luna delegation loop or any other model-specific subagent routing. Existing delegated-write containment and lifecycle safety rules remain authoritative for any later write-capable delegation.

#### Scenario: Goal is defined without critic loop

- **WHEN** a request requires goal refinement
- **THEN** the goal can be completed without spawning Luna or another model-specific critic
- **AND** implementation delegation, if later used, remains subject to the existing guarded delegation contract
