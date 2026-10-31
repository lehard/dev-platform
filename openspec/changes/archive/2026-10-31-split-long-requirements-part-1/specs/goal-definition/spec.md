## MODIFIED Requirements

### Requirement: Goal definition is selective and outcome-oriented

The platform SHALL support a transient goal-definition refinement step before OpenSpec/managed authoring when the user's request is materially fuzzy about the desired outcome or success evidence, or when the user explicitly requests goal-backed work.

#### Scenario: Fuzzy non-trivial request benefits from refinement

- **GIVEN** a non-trivial request whose intended result or validator is materially underspecified
- **WHEN** the platform prepares the request for planning or managed authoring
- **THEN** it first sharpens the request into a goal meeting the defined quality bar
- **AND** missing information that could change the intended result causes a concise clarification instead of invented requirements

#### Scenario: Concrete quick task does not need a goal

- **GIVEN** a small concrete request with an obvious completion condition
- **WHEN** normal task intake classifies it as quick execution
- **THEN** the existing quick-task lifecycle remains available without mandatory goal creation

### Requirement: Official goal semantics are adopted without false runtime claims

The platform SHALL align its goal quality semantics with the official OpenAI `define-goal` quality contract.

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

## ADDED Requirements

### Requirement: Goal definition is not required for ordinary concrete tasks

The platform SHALL NOT require the goal-definition refinement step for an ordinary concrete quick or implementation task.

#### Scenario: Ordinary concrete task

- **WHEN** the user requests an ordinary concrete quick or implementation task
- **THEN** the goal-definition refinement step is not required

### Requirement: A refined goal identifies outcome, evidence, threshold, bounds and clarification condition

A refined goal SHALL identify the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold, material scope bounds, and a condition that requires clarification rather than unbounded autonomous work.

#### Scenario: Goal is refined

- **WHEN** a goal is refined
- **THEN** it identifies the concrete outcome, verification evidence, a meaningful quantitative or binary success threshold and material scope bounds
- **AND** it identifies a condition that requires clarification rather than unbounded autonomous work

### Requirement: Explicit goal-backed requests use the native goal capability

The platform SHALL use the supported native goal capability (`/goal` or runtime-native goal tools) for explicit goal-backed requests when the agent runtime exposes it.

#### Scenario: Runtime exposes the native goal capability

- **WHEN** the user makes an explicit goal-backed request and the agent runtime exposes the native goal capability
- **THEN** the platform uses the supported native goal capability (`/goal` or runtime-native goal tools)

### Requirement: Fuzzy intake does not implicitly create durable native goal state

Materially fuzzy intake that the user did not ask to make goal-backed SHALL remain a transient refinement rather than implicitly creating durable native goal state.

#### Scenario: Fuzzy intake is not goal-backed

- **WHEN** intake is materially fuzzy and the user did not ask to make it goal-backed
- **THEN** it remains a transient refinement
- **AND** no durable native goal state is implicitly created

### Requirement: Goal integration uses the normal template distribution path

The reusable integration SHALL use the platform's normal template/Copier distribution path.

#### Scenario: Goal integration is distributed

- **WHEN** the reusable goal integration is distributed
- **THEN** it uses the platform's normal template/Copier distribution path

### Requirement: Goal integration does not claim unavailable goal-tool state

The reusable integration SHALL NOT claim successful goal-tool state when the runtime does not provide the required goal capability.

#### Scenario: Runtime lacks the goal capability

- **WHEN** the runtime does not provide the required goal capability
- **THEN** the reusable integration does not claim successful goal-tool state

### Requirement: Unavailable goal capability is replaced by equivalent refinement or reported

When the official goal capability is unavailable, the platform MAY fall back to an equivalent transient natural-language goal refinement that meets the same quality bar, or SHALL report the capability limitation explicitly.

#### Scenario: Official goal capability is unavailable

- **WHEN** the official goal capability is unavailable
- **THEN** the platform either uses an equivalent transient natural-language goal refinement that meets the same quality bar or reports the capability limitation explicitly
