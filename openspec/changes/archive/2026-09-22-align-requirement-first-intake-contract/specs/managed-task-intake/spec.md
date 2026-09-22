# managed-task-intake Specification Delta

## MODIFIED Requirements

### Requirement: Managed tasks use a versioned central intake package

An internal technical child or explicitly requested direct technical managed task SHALL be represented by a human-readable Development Backlog Issue plus exactly one supported managed OpenSpec package. The package SHALL identify its format version, source issue, target repository, OpenSpec change name, preparation commit, and required planning artifacts. A generic Business Requirement carries no managed package at fixation.

#### Scenario: ChatGPT prepares a managed task

- **WHEN** ChatGPT explicitly authors an internal technical child or direct technical managed task
- **THEN** its Issue contains a human task description and OpenSpec change name
- **AND** one `managed-openspec:v1` package contains source issue, target, preparation commit, and artifacts
- **AND** package existence alone does not start implementation

#### Scenario: Multiple supported packages are present

- **WHEN** intake finds zero packages, more than one current package, an unsupported version, or an incomplete manifest for a technical managed task
- **THEN** import fails closed with an actionable error
- **AND** no OpenSpec files are partially materialized

### Requirement: Generic fixation creates a Business Requirement without technical authoring

The platform SHALL distinguish discussion from explicit fixation. Discussion alone SHALL NOT create Backlog state. A generic instruction to fix or add accepted non-trivial work to the Development Backlog SHALL create or reuse one human-facing `type:requirement` Business Requirement containing business intent and SHALL stop. It SHALL NOT create a managed OpenSpec package, technically decompose the work, or start implementation unless the same request also clearly authorizes execution. An explicit request for a technical managed task SHALL remain eligible for the direct technical managed authoring path.

#### Scenario: User is still discussing alternatives

- **WHEN** the user and agent explore requirements, architecture, or tradeoffs without explicit fixation or execution intent
- **THEN** no Development Backlog issue or managed OpenSpec package is created solely because discussion is detailed

#### Scenario: User explicitly asks to fix the accepted change

- **WHEN** the user says “зафиксируй”, “добавь в бэклог”, “создай задачу”, or an equivalent generic authoring instruction
- **THEN** the agent creates or reuses one Business Requirement through the requirement intake contract
- **AND** no OpenSpec package, technical decomposition, managed start, dispatch, or implementation is initiated

#### Scenario: User explicitly asks for a technical managed task

- **WHEN** the user explicitly requests a technical managed task or supplies an existing technical managed Issue/OpenSpec task
- **THEN** the direct managed authoring or start path remains available under its existing package and lifecycle safeguards

### Requirement: Fresh non-trivial execution enters managed intake before implementation

When a user asks to execute a fresh non-trivial change, the platform SHALL create or reuse a Business Requirement and run requirement-first pre-authoring before implementation. Each resulting internal managed OpenSpec child SHALL be linked to the parent Requirement, started through the standard managed lifecycle, and implemented against its materialized canonical OpenSpec. Execution intent authorizes these steps without a separate fixation request. An explicitly requested direct technical managed task remains an exception.

#### Scenario: User asks Codex to implement a fresh non-trivial change

- **WHEN** the user asks to implement, fix, build, or otherwise execute a material change without supplying a technical managed task
- **THEN** the agent creates or reuses a Business Requirement, starts pre-authoring, authors and links its internal technical child or children, and starts those children
- **AND** implementation begins only after canonical OpenSpec materialization and required preflight

#### Scenario: Existing managed task already represents the execution request

- **WHEN** the user supplies an existing `type:requirement` Issue for execution
- **THEN** the platform starts or resumes that Requirement's pre-authoring state without creating a duplicate Requirement
- **AND** an explicitly supplied existing technical managed task instead follows the direct managed start/resume contract

### Requirement: Direct technical execution has one idempotent orchestration path

For an explicitly requested direct technical managed task, the platform SHALL provide a deterministic execution entry path that composes existing managed authoring and managed start. The path SHALL NOT create a competing backlog, package format, dispatcher, or lifecycle state machine. Generic fresh non-trivial execution instead enters the requirement-first path.

#### Scenario: Combined execution path succeeds from a clean state

- **WHEN** the orchestration path receives an explicitly direct technical managed execution request
- **THEN** it performs required authoring checks, creates or reuses one technical managed task, then starts/resumes that exact task
- **AND** returns the canonical task checkout/OpenSpec to the ordinary implementation lifecycle

#### Scenario: Orchestration is retried after partial progress

- **GIVEN** a previous attempt already created the Issue/package, task worktree, or materialized OpenSpec before interruption
- **WHEN** the same accepted execution is retried
- **THEN** the path resolves and reuses the existing exact managed identity
- **AND** does not create a duplicate Issue, package, worktree, or competing OpenSpec change

### Requirement: Fixation-only intent remains authoring-only

The platform SHALL distinguish recording accepted work from executing it. Generic fixation SHALL create or update a Business Requirement and stop before OpenSpec, technical decomposition, managed start, or implementation unless the same request clearly authorizes execution.

#### Scenario: User asks only to add the accepted change to Backlog

- **WHEN** the user gives an authoring-only instruction such as “зафиксируй” or “добавь в бэклог”
- **THEN** the platform creates or reuses the human-facing Business Requirement
- **AND** it does not create a technical managed task or invoke implementation lifecycle operations

### Requirement: Quick work escalates to managed intake before becoming a material OpenSpec change

Quick execution SHALL remain available for small bounded work. If quick work becomes materially behavioral, architectural, compatibility-related, data-contract-related, or cross-session in scope, or needs a full active OpenSpec change, the platform SHALL enter requirement-first intake before further implementation, except when the user explicitly requests the direct technical managed path.

#### Scenario: Representative quick fix stays bounded

- **GIVEN** a small clear change needs no full OpenSpec contract
- **WHEN** the user requests immediate execution
- **THEN** the quick lifecycle may execute without a Backlog Issue or ceremonial OpenSpec

#### Scenario: Quick task grows into a material change

- **GIVEN** work began as quick execution
- **WHEN** inspection reveals material scope or need for a full active OpenSpec contract
- **THEN** further implementation stops and the accepted scope is recorded or reused as a Business Requirement
- **AND** work continues only after pre-authoring and a linked managed technical child establish canonical OpenSpec provenance

### Requirement: Connected-GitHub authoring verifies durable managed state before reporting success

When a ChatGPT Project authors an internal or explicitly requested direct technical managed task through connected GitHub, it SHALL read back and verify the Issue, labels, and one active supported `managed-openspec:v1` package before reporting technical authoring success. Generic fixation through connected GitHub SHALL instead verify the durable Business Requirement representation without requiring or publishing any managed OpenSpec package.

#### Scenario: Connected authoring completes normally

- **WHEN** a ChatGPT Project records an accepted generic fixation request
- **THEN** it reads back the exact `type:requirement` Issue with business sections and target repository
- **AND** it reports successful fixation only after verifying that representation
- **AND** it does not publish a managed OpenSpec package or start execution

#### Scenario: Issue exists but package publication is incomplete

- **WHEN** an internal or explicitly requested direct technical managed task is authored through connected GitHub
- **THEN** the adapter reads back its exact Issue, configured labels, and one complete active `managed-openspec:v1` package
- **AND** it reports technical authoring success only after the existing package checks pass

#### Scenario: Partial state cannot be repaired safely

- **WHEN** connected technical authoring finds ambiguous or conflicting partial Issue/package state
- **THEN** it reports the exact blocker and does not claim technical authoring success
- **AND** it does not weaken managed-start validation or invent replacement product intent

## ADDED Requirements

### Requirement: Intake surfaces retain one semantic route contract

The platform SHALL automatically check key canonical and downstream agent-facing intake surfaces for semantic alignment on Discuss, generic Fix, non-trivial Execute, and explicit direct technical managed paths. A recurrence of the old claim that generic fixation immediately creates a managed task and OpenSpec package SHALL fail validation.

#### Scenario: Stale generic-fixation wording returns

- **WHEN** a key accepted spec or agent-facing surface again directs generic “зафиксируй” to create a technical managed OpenSpec package
- **THEN** the automated contract check fails with the offending surface identified

#### Scenario: Direct technical path is preserved

- **WHEN** the contract check reads the canonical and downstream agent-facing surfaces
- **THEN** it confirms explicit technical intent still selects the direct managed path

## RENAMED Requirements

- FROM: `### Requirement: Explicit fixation intent creates a managed task without starting implementation`
- TO: `### Requirement: Generic fixation creates a Business Requirement without technical authoring`

- FROM: `### Requirement: Fresh non-trivial execution has one idempotent orchestration path`
- TO: `### Requirement: Direct technical execution has one idempotent orchestration path`
