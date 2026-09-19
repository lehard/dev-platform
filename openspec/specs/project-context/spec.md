# project-context Specification

## Purpose
Define the bounded, project-owned context layer that gives coding agents stable product/domain knowledge without duplicating canonical engineering, OpenSpec, module, or operational guidance.
## Requirements
### Requirement: Managed projects expose a bounded project-owned context layer

Dev Platform SHALL provide a discoverable project-owned context layer for stable product/domain knowledge while keeping repository-wide agent guidance bounded. The project context layer SHALL complement rather than duplicate existing canonical owners for engineering rules, checks, OpenSpec behavior, module-local rules, and detailed architecture/runbook documentation.

#### Scenario: Agent reaches a project-domain concern
- **WHEN** a task requires product semantics, a project-specific domain term, an architecture invariant, a known anti-pattern, or a representative implementation example
- **THEN** the repository-wide context map exposes the relevant project-context destination
- **AND** the agent can load that bounded context without loading every detailed context document.

#### Scenario: Task is unrelated to project-domain context
- **WHEN** a task does not reach a project/domain concern represented by the context pack
- **THEN** the platform does not require the agent to ingest the whole context pack solely because it exists.

#### Scenario: Existing canonical owner already covers a concern
- **WHEN** engineering rules, test commands, accepted behavior, module-local constraints, or detailed operational guidance already have an authoritative repository owner
- **THEN** project context links to that owner instead of copying a competing version of the same contract.

### Requirement: Project-context bootstrap is evidence-first and non-inventive

The platform SHALL define a provider-neutral bootstrap/interview flow that uses existing repository evidence before asking a human to fill gaps. The flow SHALL preserve uncertainty rather than fabricating plausible project knowledge.

#### Scenario: Repository already contains usable context
- **WHEN** README, project rules, OpenSpec, code, checks, or existing docs establish a context fact
- **THEN** bootstrap uses that evidence to draft the corresponding bounded context
- **AND** does not ask the human to restate the same fact merely to complete a template.

#### Scenario: Material context remains unknown
- **WHEN** repository evidence does not establish a material product/domain/architecture fact
- **THEN** the interview asks one bounded unresolved question at a time
- **AND** an unanswered item remains explicitly unknown or TODO until confirmed
- **AND** the agent does not substitute an inferred answer as canonical context.

#### Scenario: Raw source material is supplied for bootstrap
- **WHEN** a human provides exported or copied source material for context extraction
- **THEN** the standard flow treats that raw material as temporary/machine-local input
- **AND** only reviewed distilled context is intended for repository tracking.

### Requirement: OpenSpec loads project context proportionally

OpenSpec guidance SHALL route to project context by artifact and concern instead of making the entire context pack unconditional context for every proposal, spec, design, or task list.

#### Scenario: Proposal needs product scope semantics
- **WHEN** a proposal depends on project goals, users, key scenarios, domain meaning, or explicit product invariants
- **THEN** authoring guidance routes to the relevant product/domain context before scope is finalized.

#### Scenario: Design reaches an architecture concern
- **WHEN** a design changes or relies on a project architecture invariant or prior decision
- **THEN** authoring guidance routes to the bounded architecture context and relevant canonical decision source.

#### Scenario: Task execution reaches a known anti-pattern
- **WHEN** implementation scope intersects a recorded project anti-pattern
- **THEN** task/implementation guidance makes that anti-pattern discoverable without copying unrelated project context into the task.

### Requirement: Project-owned context survives platform rollout

Project-context content authored for a managed repository SHALL be treated as project-owned and SHALL NOT be destructively replaced by normal Dev Platform/Copier updates.

#### Scenario: Existing project receives a platform update
- **GIVEN** the project has reviewed content under its project-context surface
- **WHEN** a normal platform update is applied
- **THEN** project-owned context content is preserved
- **AND** shared routing/framework improvements may still arrive through platform-owned files without overwriting that content.

### Requirement: Project context can feed reusable evidence snapshots

Dev Platform SHALL support derived Project Evidence Snapshots that consume canonical repository/project context without replacing it.

#### Scenario: Reviewed project context exists
- **WHEN** a snapshot projection needs product/domain/architecture knowledge
- **THEN** relevant `docs/context/` content may be used as evidence with stable source identity
- **AND** the snapshot remains derived/non-authoritative

#### Scenario: Project context changes
- **WHEN** a source identity used by a projection changes
- **THEN** the affected projection becomes stale
- **AND** unrelated projections are not invalidated unless their dependency evidence also changed

### Requirement: Snapshot facts preserve evidence and uncertainty

Derived semantic facts SHALL carry enough provenance to trace them to bounded sources and SHALL distinguish facts from conflicts/unknowns.

#### Scenario: Sources disagree materially
- **WHEN** authoritative-looking sources support conflicting current-system claims
- **THEN** the snapshot records the conflict or escalation need
- **AND** does not promote one unsupported interpretation to canonical project context
