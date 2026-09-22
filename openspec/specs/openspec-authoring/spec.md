# openspec-authoring Specification

## Purpose
Define the authoring, validation, archival, and evidence contract for OpenSpec changes in the platform.
## Requirements
### Requirement: Non-trivial OpenSpec proposals make the desired outcome verifiable

The platform SHALL guide non-trivial OpenSpec proposals to state the intended outcome and concrete success criteria or verification evidence. Success evidence MAY be quantitative, binary, or directly observable depending on the nature of the change. The platform SHALL NOT require invented numeric KPIs where they do not improve verification.

#### Scenario: Quantitative outcome is meaningful

- **GIVEN** a change targets latency, throughput, resource usage, accuracy, or another meaningfully measurable behavior
- **WHEN** the proposal is authored
- **THEN** it SHOULD state the relevant threshold or measurable success evidence
- **AND** semantic verification can compare the implemented result with that evidence

#### Scenario: Qualitative change has observable completion evidence

- **GIVEN** a documentation, workflow, instruction, UX, or contract change has no meaningful numeric KPI
- **WHEN** the proposal is authored
- **THEN** it MAY use concrete binary or observable acceptance evidence
- **AND** the author is not required to fabricate a numeric target

### Requirement: OpenSpec proposals preserve scope boundaries and relevant constraints

A non-trivial proposal SHALL state relevant constraints and explicit non-goals sufficient to prevent silent scope growth. When the change modifies existing behavior and the transition is not obvious from the proposal, it SHOULD include a concise current-to-target description. The platform SHALL NOT require a separate mandatory Intent artifact solely to carry this context.

#### Scenario: Existing workflow behavior changes

- **GIVEN** a change replaces or materially alters an existing workflow, UX, contract, or architecture path
- **AND** the old-to-new transition would otherwise be ambiguous
- **WHEN** the proposal is authored
- **THEN** it includes concise current and target behavior
- **AND** constraints/non-goals identify important preserved boundaries

#### Scenario: Self-contained additive change is already clear

- **GIVEN** an additive change has an unambiguous target with no useful prior-state comparison
- **WHEN** the proposal is authored
- **THEN** an empty AS-IS/TO-BE section is not required

### Requirement: OpenSpec design risk analysis is proportional to material risk

The platform SHALL require concrete risk-and-mitigation reasoning when a non-trivial design materially affects data or migrations, security/privacy, CI or release lifecycle, external integrations, backwards compatibility, cross-project rollout, or comparable high-consequence boundaries. Low-risk changes SHALL NOT be forced to add generic risk boilerplate.

#### Scenario: Materially risky platform change

- **GIVEN** a design changes a shared release, compatibility, data, security, integration, or multi-project boundary
- **WHEN** the design is authored
- **THEN** it records the material risks and corresponding mitigations
- **AND** those mitigations can inform implementation and verification

#### Scenario: Low-risk bounded change

- **GIVEN** a change has no material risk boundary beyond ordinary implementation defects
- **WHEN** the design is authored
- **THEN** the platform does not require a ceremonial risk table

### Requirement: Active OpenSpec does not become a second backlog or manual lifecycle ledger

The platform SHALL bound the accepted current iteration through scope, non-goals, specs, and tasks. It SHALL NOT require Must/Should/Could classification, future-release roadmapping, manual OpenSpec status/date/expiry fields, or artifact inventories that duplicate authoritative lifecycle state.

#### Scenario: Future improvement is outside the accepted change

- **WHEN** authoring identifies a useful later enhancement outside the accepted result
- **THEN** it remains a non-goal or follow-up
- **AND** generic explicit fixation creates or reuses a Business Requirement without creating an OpenSpec package

#### Scenario: Lifecycle state changes

- **WHEN** a change moves through verification, archive, or publication
- **THEN** authoritative lifecycle state and receipts remain the source of truth
- **AND** no manually maintained proposal status field mirrors them

### Requirement: Central and generated repositories share one OpenSpec authoring contract

Dev Platform SHALL keep the central OpenSpec authoring policy and the generated managed-project policy semantically aligned. Changes to shared authoring behavior SHALL consider both new-project rendering and reviewed Copier updates to existing managed projects.

#### Scenario: New managed project is rendered

- **WHEN** the platform renders a new managed project
- **THEN** its OpenSpec configuration carries the outcome, success-evidence, scope-boundary, conditional current-to-target, and proportional-risk guidance

#### Scenario: Existing managed project receives the policy update

- **WHEN** a reviewed Copier update applies the platform release containing this change
- **THEN** the project receives the shared authoring-policy update through the normal ownership-safe upgrade path
- **AND** no new mandatory Intent artifact or project-specific content overwrite is introduced

### Requirement: Semantic verification checks the authored outcome contract

For non-trivial changes, semantic OpenSpec verification SHALL consider whether the implementation and active artifacts satisfy the proposal's stated outcome and success evidence in addition to completeness, correctness, coherence, and current specs/deltas.

#### Scenario: Implementation satisfies tasks but misses the stated outcome

- **GIVEN** implementation tasks are checked
- **BUT** the stated success evidence is not met or cannot be demonstrated
- **WHEN** semantic verification runs
- **THEN** the change is not considered semantically complete
- **AND** a successful verification receipt is not recorded until the material gap is resolved

### Requirement: Verification receipt requirements are canonical and preflight-actionable

The canonical central OpenSpec workflow and the rendered downstream workflow SHALL describe the same platform-enforced verification receipt evidence requirements. Archive preflight SHALL detect a missing required automated-checks evidence marker before archive mutation and SHALL identify the canonical contract needed to repair it.

#### Scenario: Verification receipt omits automated-checks evidence

- **GIVEN** a change has a verification receipt without the platform-required automated-checks evidence marker
- **WHEN** archive preflight runs
- **THEN** archive mutation does not begin
- **AND** the diagnostic identifies the missing requirement and its canonical workflow location.

### Requirement: OpenSpec stable-version upgrades preserve lifecycle correctness

Dev Platform SHALL update its supported OpenSpec compatibility baseline only after the selected stable release passes representative managed lifecycle checks and focused regressions for correctness-sensitive upstream changes.

#### Scenario: Stable OpenSpec upgrade passes compatibility checks
- **WHEN** a newer stable OpenSpec release is selected for adoption
- **AND** representative materialize, validate, semantic verify and archive checks pass
- **AND** focused regressions for the motivating upstream correctness changes pass
- **THEN** the platform MAY update its minimum/tested OpenSpec version contract and matching fixtures/docs consistently
- **AND** SHALL retain platform semantic verification and lifecycle evidence unless a separate reviewed change proves a guard redundant

#### Scenario: Compatibility check finds a material regression
- **WHEN** the selected stable OpenSpec release violates a Dev Platform lifecycle invariant or fails a representative regression
- **THEN** the platform SHALL keep the existing supported contract
- **AND** SHALL record the incompatibility instead of weakening verification, archive, or source-of-truth guarantees merely to complete the dependency bump

### Requirement: OpenSpec proposal authoring can consume atomic intents

For work routed through the ADD/intents pipeline, OpenSpec authoring SHALL treat an intent as the normalized unit of pre-authoring input while using the approved ADD and current-system evidence as referenced constraints.

#### Scenario: Atomic intent is authored
- **WHEN** an intent is ready for OpenSpec
- **THEN** proposal authoring receives the business goal/context, the intent's bounded outcome/scope/non-goals/dependencies, and ADD/evidence references
- **AND** it does not require another broad architecture discovery pass

#### Scenario: One intent has an independent observable outcome
- **WHEN** an intent can be accepted, verified, delivered, or rolled back independently
- **THEN** it SHOULD be authored as its own OpenSpec change

#### Scenario: Several intents are inseparable
- **WHEN** several intents genuinely lack independent observable outcomes and are jointly required for one coherent change
- **THEN** they MAY be authored as one OpenSpec change
- **AND** the ordinary OpenSpec split test must justify that grouping rather than convenience alone

### Requirement: OpenSpec authoring preserves approved ADD decisions

OpenSpec authoring SHALL refine the implementation contract without silently replacing material system decisions already approved in ADD.

#### Scenario: Design remains within ADD
- **WHEN** OpenSpec `design.md` adds implementation detail consistent with the approved ADD
- **THEN** authoring proceeds normally

#### Scenario: Design requires a conflicting material decision
- **WHEN** OpenSpec authoring discovers that the approved ADD is insufficient or must materially change
- **THEN** the gap is returned to ADD/intent refinement before implementation
- **AND** proposal/design does not silently become the first place that new consequential architecture is decided

### Requirement: ADD/intents do not create a second OpenSpec lifecycle

After materialization, ordinary managed OpenSpec lifecycle rules SHALL govern implementation, verification, archive, and publication.

#### Scenario: Managed OpenSpec exists
- **WHEN** the intent has been materialized into an OpenSpec change
- **THEN** no ADD-specific implementation status, archive state, or second backlog is required

### Requirement: Atomic intents have a bounded executable authoring handoff

For work routed through ADD/Intents, the platform SHALL provide a bounded authoring-input representation for a selected ready intent or explicitly justified cohesive intent group.

#### Scenario: Ready intent is prepared for OpenSpec
- **WHEN** the intent passes parent-binding and readiness gates
- **THEN** the handoff contains business context reference, outcome, scope/non-goals, dependencies, approved ADD digest/material constraints, and snapshot/evidence references
- **AND** OpenSpec authoring need not repeat broad architecture discovery

#### Scenario: Intent or parent changes after handoff
- **WHEN** the selected intent, approved ADD, or required snapshot identity no longer matches the handoff
- **THEN** the authoring input is stale and must be regenerated before relying on it
