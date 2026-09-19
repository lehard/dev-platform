# agent-workflow Specification

## Purpose
Define the end-to-end agent workflow for disciplined task intake, implementation, verification, and delivery.
## Requirements
### Requirement: Unknown defects use evidence-first diagnosis

Dev Platform SHALL provide a reusable diagnosis path for unknown bugs, regressions and unexplained failures that establishes an observable failure condition and tests falsifiable hypotheses before claiming a root cause.

#### Scenario: Unknown failure is investigated
- **WHEN** an agent is diagnosing an unknown bug or regression
- **THEN** it establishes a reproducible or otherwise directly evidenced failure condition before claiming root cause
- **AND** tests bounded falsifiable hypotheses before applying the final production fix

#### Scenario: Failure cannot be reproduced or evidenced
- **WHEN** the reported failure condition cannot be reproduced or otherwise confirmed
- **THEN** the agent reports the diagnosis as unconfirmed
- **AND** does not present a plausible hypothesis as proven root cause

### Requirement: Diagnosis closes with regression evidence where feasible

When a reasonable test seam exists, diagnosis SHALL produce a regression check that demonstrates the defect before the fix and passes after the fix, and SHALL re-run the original failure path after repair.

#### Scenario: Reasonable regression seam exists
- **WHEN** the diagnosed defect can be captured by a bounded automated test
- **THEN** the test demonstrates failure before the repair and success after it
- **AND** the original reproducer is re-run after the repair

#### Scenario: No reasonable regression seam exists
- **WHEN** capturing the defect requires disproportionate or invalid test coupling
- **THEN** the limitation is recorded explicitly rather than fabricating regression evidence

### Requirement: Material domain ambiguity can trigger selective pre-design interrogation

Dev Platform SHALL support an optional refinement path for materially ambiguous or domain-heavy managed work that resolves evidence-answerable questions first and surfaces only unresolved choices that can materially affect the intended outcome.

#### Scenario: Repository evidence resolves ambiguity
- **WHEN** a candidate ambiguity can be answered from authoritative repository or provided domain evidence
- **THEN** the agent resolves it from that evidence before asking the user

#### Scenario: Product choice remains unresolved
- **WHEN** available evidence cannot resolve a choice that would materially change the intended outcome
- **THEN** the agent surfaces that choice for human resolution before implementation proceeds on an invented assumption

#### Scenario: Request is already concrete
- **WHEN** a non-trivial request has a sufficiently clear outcome and domain model for safe authoring/execution
- **THEN** the platform does not require a separate interrogation ceremony

### Requirement: Domain refinement does not create a competing implementation contract

Accepted refinement SHALL be recorded in the existing managed OpenSpec artifacts and SHALL NOT require a parallel context, ADR, status or planning ledger as an authoritative source.

#### Scenario: Refinement is complete
- **WHEN** the material ambiguity is resolved
- **THEN** the accepted decision is incorporated into proposal/spec/design as appropriate
- **AND** materialized OpenSpec remains canonical for implementation and verification

### Requirement: Work can be continued through an optional interoperable handoff

Dev Platform SHALL support an optional, provider-neutral navigation envelope for
continuing live work in another agent, provider, or human context without
duplicating canonical task state, materialized only through the shared optional
engineering capability lifecycle.

#### Scenario: Context moves to another agent, provider, or person
- **WHEN** live work must continue in a context that cannot be reached by an ordinary same-context compact
- **THEN** the envelope identifies repository, exact revision, applicable workspace, managed task/OpenSpec, the provider routing record when one exists, canonical evidence, verified facts, unresolved assumptions, blockers, and next intent

#### Scenario: Same-context compaction is sufficient
- **WHEN** work remains in the same context
- **THEN** no durable handoff artifact is required

#### Scenario: No separate lifecycle is introduced
- **WHEN** the handoff capability is provided
- **THEN** it consumes the shared optional-capability identity, provenance, opt-in, materialization, and update/removal surfaces
- **AND** introduces no handoff-specific registry, configuration, or update lifecycle

### Requirement: Handoff preserves truth and freshness

A handoff SHALL keep verified facts distinct from assumptions, and the receiver
SHALL validate referenced identity before relying on the envelope.

#### Scenario: Revision or task identity changed
- **WHEN** the repository revision or managed task identity referenced by the envelope no longer matches current state
- **THEN** the handoff is treated as stale and canonical sources are re-read before work continues

#### Scenario: Claim lacks evidence
- **WHEN** a statement in the handoff is not supported by cited evidence
- **THEN** it is recorded as an unresolved assumption and is not presented as a verified fact

#### Scenario: A canonical reference is missing or unresolvable
- **WHEN** a referenced canonical artifact cannot be located at the given revision
- **THEN** the receiver surfaces it as a missing reference rather than proceeding on the envelope's prose

### Requirement: Handoff grants no authority and does not duplicate routing

Creating or receiving a handoff SHALL NOT start work, grant write access, or
mutate managed task, OpenSpec, GitHub, or Project state, and SHALL compose with
the existing provider routing handoff rather than replace it.

#### Scenario: Receiving a handoff
- **WHEN** an agent or person receives a handoff envelope
- **THEN** no work is started and no lifecycle, GitHub, or Project state changes until execution is explicitly requested through the normal managed entrypoints

#### Scenario: Creating a handoff
- **WHEN** an agent produces a handoff envelope
- **THEN** it only records navigation context and performs no branch, worktree, commit, comment, or status mutation

#### Scenario: Executor selection is already owned by routing
- **WHEN** a managed task already has a provider routing record
- **THEN** the handoff references that record and does not restate executor selection or write containment or launch an executor

### Requirement: Material business requirements can be translated through Architecture Design Delta

Dev Platform SHALL support a bounded pre-OpenSpec path that derives an Architecture Design Delta (ADD) when a business requirement introduces or changes material system-design concerns not already determined by the accepted system.

#### Scenario: Requirement introduces new system design
- **WHEN** a business requirement implies new or changed capabilities, boundaries, contracts, data ownership, invariants, security/trust concerns, or material non-functional behavior
- **THEN** the platform derives a structured ADD relative to current accepted evidence
- **AND** the ADD records only the new or changed consequences

#### Scenario: Existing system already determines a choice
- **WHEN** accepted OpenSpec, an active delta, relevant project context, code/tests, or another authoritative source determines the applicable choice
- **THEN** ADD references that existing constraint
- **AND** does not present it as a new design decision

#### Scenario: Clear change has no useful design delta
- **WHEN** a bounded change introduces no material system-design delta
- **THEN** the platform does not require ADD/intents ceremony

### Requirement: ADD approval resolves consequential ambiguity before decomposition

The ADD path SHALL reuse evidence-first domain interrogation and SHALL expose only unresolved consequential choices to the human.

#### Scenario: Evidence answers the question
- **WHEN** bounded authoritative evidence resolves a candidate ambiguity
- **THEN** the platform records the resolution without asking the human

#### Scenario: Consequential choice remains unresolved
- **WHEN** alternatives would materially change the system delta and evidence cannot determine the intended choice
- **THEN** the choice and material consequences are surfaced for human resolution
- **AND** the ADD is not treated as approved while the consequential choice remains open

### Requirement: Approved ADD decomposes into atomic intents

After ADD approval, Dev Platform SHALL support a separate decomposition pass that produces bounded intents without reopening design decisions already established by the ADD.

#### Scenario: ADD is decomposed
- **WHEN** an approved ADD contains multiple separable system/business outcomes
- **THEN** decomposition produces atomic intents with explicit scope, non-goals, dependencies, and references to the relevant ADD/evidence
- **AND** uses the original business requirement for goal/context rather than as permission to redesign the system independently of ADD

#### Scenario: Decomposition discovers a missing design decision
- **WHEN** an intent cannot be bounded without inventing or changing a material system decision
- **THEN** decomposition returns that gap to ADD refinement
- **AND** does not silently settle it inside the intent

### Requirement: Intent coverage and boundaries are inspectable

The intent set SHALL make ADD coverage and dependency structure inspectable without claiming that deterministic checks prove semantic completeness.

#### Scenario: Material ADD consequence is represented
- **WHEN** ADD contains a material new/changed consequence
- **THEN** the intent set links that consequence to at least one intent or records an explicit non-implementation disposition

#### Scenario: Intents overlap materially
- **WHEN** two intents own the same material responsibility without an explicit reason
- **THEN** decomposition is treated as needing refinement

#### Scenario: Deterministic gates pass
- **WHEN** schema, linkage, dependency, provenance, or freshness checks pass
- **THEN** the platform may claim those structural properties
- **BUT** does not claim semantic completeness solely from deterministic validation

### Requirement: Intents are the normalized input to OpenSpec authoring

OpenSpec authoring SHALL consume atomic intents rather than using ADD directly as the normal specification unit.

#### Scenario: Intent is ready for authoring
- **WHEN** an intent has bounded outcome, scope/non-goals, dependencies, and ADD/evidence references
- **THEN** it can be handed to OpenSpec proposal authoring
- **AND** authoring does not repeat broad system/design discovery merely to rediscover the approved delta

#### Scenario: OpenSpec authoring finds a material ADD conflict
- **WHEN** proposal/spec/design authoring requires changing an approved ADD decision
- **THEN** the flow returns to ADD/intent refinement
- **AND** does not silently override the approved design

### Requirement: ADD and intents are pre-authoring evidence, not competing lifecycle authorities

ADD and intents SHALL NOT introduce a second backlog, implementation contract, release lifecycle, or current-system registry.

#### Scenario: OpenSpec is materialized
- **WHEN** an intent has produced a managed OpenSpec change
- **THEN** that OpenSpec is canonical for implementation and verification
- **AND** ADD/intents remain bounded provenance rather than independently synchronized current-state ledgers

#### Scenario: OpenSpec is archived
- **WHEN** the change is successfully archived
- **THEN** accepted specs plus implementation/project context form the future system baseline
- **AND** future ADD analysis uses that baseline rather than old intent prose as authority

### Requirement: Greenfield baseline precedes incremental ADD

Dev Platform SHALL treat ADD as an incremental evolution mechanism rather than requiring an upfront ADR set for a new project.

#### Scenario: New project is bootstrapped
- **WHEN** the technology stack is selected and a project skeleton exists
- **THEN** an initial accepted OpenSpec baseline is derived from intended requirements plus the concrete skeleton/system context
- **AND** later material business requirements may use ADD → intents relative to that baseline

