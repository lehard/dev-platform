## ADDED Requirements

### Requirement: Fresh non-trivial execution enters managed intake before implementation

When a user explicitly asks a repository agent to execute a fresh non-trivial change that is not already represented by a managed task, the platform SHALL establish managed-task provenance before implementation begins. Execution intent SHALL authorize the platform to author or reuse the managed task and then start that same task without requiring a second user instruction between those steps.

#### Scenario: User asks Codex to implement a fresh non-trivial change

- **GIVEN** the request is material enough for the managed path
- **AND** no unambiguous existing managed task already represents the accepted change
- **WHEN** the user asks to implement, fix, build, or otherwise execute the change
- **THEN** the agent performs the bounded managed-authoring preflight and creates one Development Backlog Issue plus supported managed OpenSpec package
- **AND** starts or resumes that exact managed task through the standard managed-start lifecycle
- **AND** implementation changes begin only after the repository-local canonical OpenSpec has been materialized and preflighted
- **AND** the user is not required to separately say “зафиксируй” after already requesting execution

#### Scenario: Existing managed task already represents the execution request

- **GIVEN** bounded duplicate/identity checks resolve one existing managed task as the same accepted change
- **WHEN** the user asks to execute the change
- **THEN** the platform reuses that task rather than creating a duplicate
- **AND** continues through the existing managed start/resume contract

### Requirement: Fixation-only intent remains authoring-only

The platform SHALL distinguish an instruction to record accepted work from an instruction to execute it. Explicit fixation SHALL continue to create or update the managed task and SHALL stop before managed start or implementation unless the same current request also clearly authorizes execution.

#### Scenario: User asks only to add the accepted change to Backlog

- **WHEN** the user says “зафиксируй”, “добавь в бэклог”, “создай задачу” or an equivalent authoring-only instruction
- **THEN** the platform authors or updates the managed task and package
- **AND** does not invoke managed start, apply, implementation, dispatch, or publication

### Requirement: Quick work escalates to managed intake before becoming a material OpenSpec change

Quick execution SHALL remain available for small bounded work that does not require a managed planning contract. If quick work becomes materially behavioral/architectural/compatibility/data-contract/cross-session in scope, or the agent determines that a full active OpenSpec change is required to govern the implementation, the platform SHALL transition to managed intake before further implementation continues.

#### Scenario: Representative quick fix stays bounded

- **GIVEN** a small clear change does not require a full OpenSpec implementation contract
- **WHEN** the user asks for immediate execution
- **THEN** the existing quick lifecycle may execute without Development Backlog Issue or ceremonial OpenSpec

#### Scenario: Quick task grows into a material change

- **GIVEN** work started as quick execution
- **WHEN** repository inspection reveals material scope or the need for a full active OpenSpec change
- **THEN** further implementation stops
- **AND** the accepted scope is authored/reused as a managed task
- **AND** work continues only after managed start establishes canonical repository-local OpenSpec provenance

### Requirement: Fresh non-trivial execution has one idempotent orchestration path

The platform SHALL provide a standard deterministic orchestration entry path for fresh non-trivial execution that composes the existing managed authoring and managed-start operations. The orchestration path SHALL NOT create a competing backlog, package format, dispatcher, or lifecycle state machine.

#### Scenario: Combined execution path succeeds from a clean state

- **WHEN** the orchestration path receives a fresh non-trivial accepted execution request
- **THEN** it performs required authoring checks, creates or reuses one managed task, then starts/resumes that exact task
- **AND** returns the canonical task checkout/OpenSpec to the ordinary implementation lifecycle

#### Scenario: Orchestration is retried after partial progress

- **GIVEN** a previous attempt already created the Issue/package, task worktree, or materialized OpenSpec before interruption
- **WHEN** the same accepted execution is retried
- **THEN** the path resolves and reuses the existing exact managed identity
- **AND** does not create a duplicate Issue, package, worktree, or competing OpenSpec change

### Requirement: Ordinary active OpenSpec execution is backed by managed provenance

On normal platform-owned execution and delivery paths, a non-trivial active OpenSpec implementation SHALL have matching managed-task provenance. The platform SHALL fail closed before terminal execution/publication when an active non-trivial OpenSpec change lacks that provenance, except through an explicit supported legacy/recovery path that identifies the state without inventing history.

#### Scenario: Orphan active OpenSpec reaches the ordinary lifecycle

- **GIVEN** a non-trivial active OpenSpec change exists
- **AND** no matching managed source Issue/provenance can be resolved
- **WHEN** the ordinary platform-owned completion/publication lifecycle evaluates the task
- **THEN** it blocks with an actionable managed-intake or recovery instruction
- **AND** does not fabricate a source Issue, silently bypass provenance, delete work, or report terminal success

#### Scenario: Genuine quick work has no OpenSpec change

- **GIVEN** a bounded quick task never created an active OpenSpec change
- **WHEN** it uses the supported quick lifecycle
- **THEN** absence of managed provenance alone does not force backlog creation

### Requirement: Shared intake semantics remain updateable in existing managed repositories

Dev Platform SHALL keep mutable cross-project task-intake detail in a platform-owned canonical contract that is delivered by normal platform releases. Project-owned root agent guidance MAY keep project/domain rules and a bounded always-on map, but SHALL expose a stable reference/invariant that routes agents to the shared intake contract instead of freezing a divergent copy of the workflow.

#### Scenario: New managed project is rendered

- **WHEN** a new project is created from the Dev Platform template
- **THEN** its repository agent map and platform-owned intake contract expose the same discuss/fix/quick/fresh-nontrivial/existing-managed semantics as the central platform

#### Scenario: Existing managed project has stale project-owned root guidance

- **GIVEN** the project already has managed-task capability/configuration
- **BUT** its project-owned root guidance predates the shared execution-intake contract
- **WHEN** the platform migration/update is applied
- **THEN** the required stable reference/invariant to the platform-owned intake contract is reconciled without overwriting unrelated project/domain/module rules
- **AND** subsequent shared intake updates can arrive through normal platform-owned rollout surfaces

#### Scenario: Jara_Fin receives the migration

- **GIVEN** `Jara_Fin` already exposes Development Backlog configuration and managed-task scripts
- **AND** its root project guidance contains older intake semantics
- **WHEN** the release containing this change is rolled out/migrated
- **THEN** Codex and Claude in that repository resolve the new shared intake contract before starting fresh non-trivial execution
- **AND** existing Jara-specific engineering/domain instructions remain intact

### Requirement: First-time project adoption remains an explicit boundary

Changing the shared intake contract SHALL NOT automatically adopt repositories that are not yet managed by Dev Platform. Candidate repositories SHALL continue to use the existing explicit first-time adoption process before they receive managed rollout semantics.

#### Scenario: Candidate repository is present in the managed registry

- **GIVEN** a repository is marked `candidate` rather than `managed`
- **WHEN** a new intake-contract release is published
- **THEN** ordinary rollout does not mutate or reclassify that repository
- **AND** explicit Adopt Project remains the required first-time administrative action
