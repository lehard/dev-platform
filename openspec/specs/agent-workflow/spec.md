# agent-workflow Specification

## Purpose
TBD - created by archiving change add-systematic-bug-diagnosis-protocol. Update Purpose after archive.
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

