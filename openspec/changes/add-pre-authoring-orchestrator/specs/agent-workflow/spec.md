# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Pre-authoring stages can be orchestrated through one resumable flow

Dev Platform SHALL support a thin pre-authoring orchestration path that composes snapshot, ADD, intent-decomposition and OpenSpec-handoff primitives without replacing their owning contracts.

#### Scenario: Fresh end-to-end pre-authoring run
- **WHEN** a material business requirement enters the orchestrated path
- **THEN** the flow performs deterministic snapshot preflight/reuse, ADD analysis/approval, intent decomposition/gates, and OpenSpec authoring handoff in dependency order
- **AND** normal managed OpenSpec lifecycle remains responsible for implementation after materialization

#### Scenario: Completed upstream stage remains fresh
- **WHEN** execution resumes after interruption and the stage's bound upstream identities still match
- **THEN** that stage is reused
- **AND** the orchestrator does not repeat model work solely because the process/session restarted

#### Scenario: Upstream content changes
- **WHEN** a snapshot, approved ADD, or intent dependency changes
- **THEN** the orchestrator invalidates the affected downstream stages
- **AND** resumes from the earliest stage whose content-bound preconditions no longer hold

### Requirement: Human decisions are mediated by the main orchestration context

Stage workers SHALL surface unresolved consequential decisions rather than independently approving them on the user's behalf.

#### Scenario: ADD worker needs a material choice
- **WHEN** bounded evidence cannot determine a consequential alternative
- **THEN** the worker returns a structured question with evidence/alternatives/consequences to the orchestrating agent
- **AND** only the accepted human answer is applied through the ADD refinement/approval contract

#### Scenario: No human choice is needed
- **WHEN** evidence and accepted requirements determine the result
- **THEN** the flow continues without ceremonial user interaction

### Requirement: Pre-authoring resume state is bounded and non-authoritative

The orchestrator MAY preserve a machine-local ignored receipt containing identities/status needed to resume, but SHALL NOT create a second backlog, implementation state machine, or current-system authority.

#### Scenario: Run receipt is present
- **WHEN** a later session resumes the flow
- **THEN** it verifies requirement/repository/snapshot/ADD/intent/handoff identities before reuse
- **AND** treats missing or ambiguous identity as stale rather than assuming completion

### Requirement: Stage routing composes with existing model-routing policy

The orchestrator SHALL use deterministic operations where possible and existing routing/delegation primitives for model work.

#### Scenario: Snapshot extraction is routine
- **WHEN** the snapshot stage needs bounded read-only semantic extraction
- **THEN** it uses the existing routine/read-only worker path where supported

#### Scenario: Design stage needs stronger reasoning
- **WHEN** an existing hard escalation trigger or repeated substantive failure occurs
- **THEN** the flow escalates through the existing routing contract
- **AND** does not implement an independent retry/router policy

