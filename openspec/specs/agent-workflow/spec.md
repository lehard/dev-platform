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

Accepted refinement SHALL be recorded in existing managed OpenSpec artifacts and SHALL NOT require a parallel context, ADR, status or planning ledger as an authoritative implementation source. A repository decision registry MAY preserve consequential historical rationale and revisit conditions, but SHALL NOT override OpenSpec's accepted executable behavior or active deltas.

#### Scenario: Refinement is complete

- **WHEN** material ambiguity is resolved
- **THEN** the accepted behavior is incorporated into proposal/spec/design as appropriate
- **AND** materialized OpenSpec remains canonical for implementation and verification
- **AND** a relevant historical decision record may retain the rationale without becoming a second implementation contract

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

OpenSpec authoring SHALL consume atomic intents rather than using ADD directly as the normal specification unit. The handoff SHALL retain the complete accepted Requirement business context as bounded authoring input.

#### Scenario: Intent is ready for authoring

- **WHEN** an intent has bounded outcome, scope/non-goals, dependencies, and ADD/evidence references
- **THEN** its handoff includes the complete accepted Requirement business context plus the intent and approved ADD constraints
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

### Requirement: Reusable evidence projections are checked before semantic rediscovery

For workflows that opt into Project Evidence Snapshots, the platform SHALL perform deterministic freshness/invalidation preflight before invoking an agent to rebuild semantic project context.

#### Scenario: Projection inputs are unchanged
- **WHEN** every relevant source identity for a projection still matches
- **THEN** the fresh projection is reused
- **AND** no model call is required solely to rediscover the same project facts

#### Scenario: Only one projection dependency changes
- **WHEN** a bounded source change affects one projection and dependency metadata proves other projections unaffected
- **THEN** only the affected projection requires rebuilding

#### Scenario: Snapshot revision is stale
- **WHEN** the consumer cannot prove the snapshot/projection applicable to current repository evidence
- **THEN** it treats that projection as stale and refreshes or escalates before relying on it

### Requirement: Snapshots remain bounded derived state

Project Evidence Snapshots SHALL NOT create a backlog, lifecycle authority, or canonical architecture registry.

#### Scenario: Snapshot exists
- **WHEN** an agent later authors OpenSpec or performs another managed action
- **THEN** canonical repository sources retain their existing authority
- **AND** the snapshot is only evidence/cache input

### Requirement: ADD and Intent artifacts form a content-bound integrity chain

The pre-authoring pipeline SHALL bind each downstream artifact to the exact upstream evidence/content it reviewed.

#### Scenario: ADD is approved
- **WHEN** the human approves an ADD
- **THEN** approval records the exact ADD content digest and applicable snapshot/projection identity
- **AND** a later material ADD mutation invalidates that approval

#### Scenario: Intent set is created
- **WHEN** an approved ADD is decomposed
- **THEN** the intent set records the approved ADD digest and relevant snapshot/projection digest
- **AND** validation rejects a mismatched or stale parent binding

#### Scenario: Required evidence is stale
- **WHEN** the required snapshot/projection or ADD identity can no longer be proven current for decomposition
- **THEN** decomposition stops for refresh/semantic preflight
- **AND** stale state is not merely reported as a successful warning

### Requirement: Semantic intent decomposition stays inside approved design

Intent decomposition SHALL apply semantic atomicity review without inventing new material architecture behind the ADD.

#### Scenario: Candidate intent contains independent outcomes
- **WHEN** an intent combines outcomes with materially different triggers, policies, verification/delivery boundaries, or rollback independence
- **THEN** the decomposition stage treats it as a split/refinement candidate

#### Scenario: Missing design blocks decomposition
- **WHEN** an intent cannot be bounded without a new consequential system decision
- **THEN** the flow returns to ADD refinement
- **AND** the intent stage does not silently decide it

### Requirement: Ready intents satisfy the documented normalized input contract

A ready intent SHALL have a bounded outcome, explicit scope/non-goals representation, valid covered ADD references, dependencies, evidence/constraint references where applicable, and no unresolved blocker.

#### Scenario: Required intent contract is absent
- **WHEN** a ready intent is missing required normalized-input fields or has invalid references
- **THEN** deterministic validation rejects readiness before OpenSpec authoring

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

### Requirement: A business requirement is a durable human-facing object distinct from OpenSpec

Dev Platform SHALL support recording an accepted business requirement as one Development Backlog Issue (`type:requirement`) containing only business-language content, with no OpenSpec proposal/design/tasks required at authoring time.

A newly created Requirement SHALL also carry exactly one `project:*` label and exactly one `priority:*` label resolved from the target repository's existing `[development_backlog]` configuration: `project_label`, and the explicitly requested priority or `default_priority`. No separate routing source or default SHALL be introduced. Missing or conflicting routing SHALL fail closed, and creation SHALL be reported successful only after a read-back verifies those labels.

#### Scenario: Requirement authored without OpenSpec
- **WHEN** a business requirement is accepted for fixation
- **THEN** it is recorded as one `type:requirement` Issue with outcome/context/acceptance-evidence/target-repository content
- **AND** no OpenSpec proposal, design, tasks, or technical decomposition is required to create it

#### Scenario: Requirement receives configured Backlog routing
- **GIVEN** the target repository configures `development_backlog.project_label` and `default_priority`
- **WHEN** `requirement_intake.py create` records a Requirement without an explicit priority
- **THEN** the Issue carries `type:requirement`, exactly the configured `project:*` label and exactly `priority:<default_priority>`
- **AND** creation succeeds only after reading those labels back from the Issue

#### Scenario: Requirement routing is missing or conflicting
- **WHEN** the target repository's project label is not configured in the creating checkout, the Backlog repository disagrees with configuration, or a configured label is unavailable
- **THEN** creation stops before any Issue is created
- **AND WHEN** a created Issue reads back with a different `project:*` or `priority:*` label
- **THEN** the exact Issue is reported and fixation is not reported successful

### Requirement: A Requirement can start and resume pre-authoring

Dev Platform SHALL provide one entrypoint that binds a Requirement identity to the pre-authoring orchestrator so analysis can begin and resume across sessions. The binding SHALL include the canonical values of Outcome, Context when present, Acceptance evidence when present, Exclusions when present, and target repository; it SHALL NOT bind only Outcome.

#### Scenario: Requirement bridges into pre-authoring

- **WHEN** `requirement_intake.py start` is given a Requirement reference
- **THEN** it extracts the Requirement's Outcome, Context, Acceptance evidence, Exclusions, and target repository from the Issue body
- **AND** initializes the pre-authoring orchestrator with a digestable canonical representation under the Requirement's stable identity

#### Scenario: Meaningful Requirement content changes before materialization

- **GIVEN** a Requirement has local pre-authoring artifacts but no canonical managed OpenSpec materialization
- **WHEN** a later start observes a changed Outcome, Context, Acceptance evidence, Exclusions, or target repository
- **THEN** it invalidates dependent derived pre-authoring state before reuse
- **AND** it does not continue design or handoff from the stale business meaning

#### Scenario: Requirement content is unchanged on resume

- **GIVEN** a Requirement's complete canonical business representation is unchanged
- **WHEN** pre-authoring resumes
- **THEN** existing snapshot, ADD, intent, and handoff artifacts remain eligible for their normal content/freshness checks
- **AND** the flow does not repeat semantic work solely because the session restarted

### Requirement: Internal managed OpenSpec changes remain linked to their parent Requirement

Dev Platform SHALL link every internal managed OpenSpec change produced from a Requirement's pre-authoring back to that Requirement, and SHALL label it distinctly from the Requirement itself.

#### Scenario: A ready intent produces a linked internal change
- **WHEN** a handoff-ready intent is materialized into a managed OpenSpec Issue
- **THEN** that Issue is labeled `type:internal-change`
- **AND** the parent Requirement's children block records a reference to it
- **AND** the child Issue records a back-reference to its parent Requirement

#### Scenario: One Requirement produces multiple internal changes
- **WHEN** a Requirement's pre-authoring yields more than one ready intent
- **THEN** each materializes as its own linked `type:internal-change` Issue
- **AND** the main human-facing board is not required to treat them as unrelated top-level work

### Requirement: Requirement progress is derived, not duplicated

Dev Platform SHALL derive a Requirement's aggregate progress by reading its linked children's existing Development Backlog Project status, and SHALL NOT introduce a second status field, backlog, or state machine to track it.

#### Scenario: Aggregate reflects real child lifecycle
- **WHEN** `requirement_intake.py aggregate` is run for a Requirement with linked children
- **THEN** it reports a status derived only from each child's current Project status
- **AND** it writes no separate status value that could diverge from that source of truth

#### Scenario: Unreadable child status fails closed
- **WHEN** a linked child's Project status cannot be read
- **THEN** the aggregate reports that child as unknown rather than assuming it is done or in progress

### Requirement: Requirement pre-authoring is proportional and provider-neutral

Dev Platform SHALL select and record the least ceremonial safe pre-authoring depth from the complete Requirement and scoped repository evidence. The selection SHALL compose with the existing provider-neutral routing policy and SHALL NOT introduce a second router or provider-specific lifecycle.

#### Scenario: Deterministic work bypasses semantic design stages

- **WHEN** a complete Requirement and its bounded repository evidence yield a deterministic action with no material design delta
- **THEN** the flow records the deterministic depth and next action without invoking a model or requiring ADD/intents
- **AND** a resumed run can reuse that recorded decision while its bindings remain fresh

#### Scenario: Bounded evidence work uses the routine read-only path

- **WHEN** the flow needs bounded evidence extraction but no material design decision
- **THEN** it requests only the scoped projections needed for that extraction
- **AND** it records the existing routine read-only route rather than escalating to design routing

#### Scenario: Material design work proceeds through ADD and intents

- **WHEN** scoped evidence leaves a genuine architecture, behavior, compatibility, or execution design delta
- **THEN** the flow records that reason and requires ADD/intents under the existing R2 default
- **AND** it escalates to R3 only for a documented existing hard trigger

#### Scenario: Explicit skip and scoped evidence remain resumable

- **WHEN** ADD/intents are safely skipped or a matching scoped projection is already fresh
- **THEN** the flow persists a bounded receipt with its source/evidence bindings
- **AND** a changed binding invalidates only the decision and artifacts that depended on it

### Requirement: Ready Requirement handoffs materialize idempotently into linked internal changes

Dev Platform SHALL materialize a validated ready handoff through the existing managed-task intake boundary and SHALL return success only when the exact internal managed change and its parent Requirement linkage are both confirmed.

#### Scenario: A ready handoff creates one linked internal change

- **WHEN** a validated ready handoff is materialized for a Requirement
- **THEN** the adapter renders the existing managed-task package contract and creates or exactly reuses one internal managed Issue
- **AND** it immediately confirms the parent-to-child and child-to-parent linkage before reporting success

#### Scenario: Retry repairs an interrupted linkage without duplication

- **GIVEN** a prior materialization created its exact child but did not complete linkage
- **WHEN** the same handoff is retried
- **THEN** the adapter resolves that exact child by stable handoff identity and repairs the missing link
- **AND** it does not create another managed Issue or canonical OpenSpec change

#### Scenario: Invalid or ambiguous materialization fails safely

- **WHEN** handoff bindings are invalid or candidate provenance is ambiguous
- **THEN** materialization stops with actionable failure evidence
- **AND** it does not report a partial Issue/link pair as successful

### Requirement: Requirement progress is a derived human-facing projection

Dev Platform SHALL expose the Requirement's pre-authoring and child-execution progress as a recomputable read-through projection. It SHALL NOT create or mutate a second manual Requirement lifecycle state.

#### Scenario: Pre-authoring and readiness are visible before children exist

- **WHEN** a Requirement has current local orchestrator evidence and no linked internal child
- **THEN** the projection distinguishes active pre-authoring/design, a human decision gate when applicable, and implementation readiness
- **AND** it identifies the evidence used for that display stage

#### Scenario: Linked child lifecycle determines implementation and completion

- **WHEN** a Requirement has linked internal changes with authoritative lifecycle observations
- **THEN** the projection reports implementation while required children are active and completion only when all required children are complete
- **AND** it keeps internal changes out of the primary human-facing Project view

#### Scenario: Unreadable or contradictory source state is not optimistic

- **WHEN** required orchestrator or linked-child source state is missing, stale, unreadable, contradictory, or explicitly blocked
- **THEN** the projection reports blocked or unknown with the diagnostic reason
- **AND** it does not present the Requirement as ready or complete

### Requirement: Platform friction promotion executes from a recorded event

The platform SHALL allow an operator to promote a recorded `scope=platform` friction event to the configured operator issue repository without a runtime configuration error. The promoted body SHALL retain the existing sanitized metadata and omit raw evidence.

#### Scenario: Operator dry-runs promotion

- **GIVEN** a recorded platform event and a configured promotion repository
- **WHEN** the operator runs `agent_friction.py promote <event> --dry-run`
- **THEN** the command exits successfully and prints the sanitized candidate with the source project identity
- **AND** no GitHub issue is created

#### Scenario: Promotion configuration is absent

- **WHEN** the operator runs promotion without `promotion.repo`
- **THEN** the command reports the missing operator setting before an issue mutation

### Requirement: Confirmed handoff materialization has a successful machine-readable CLI result

Dev Platform SHALL return a successful machine-readable CLI result only when the exact internal managed change and its parent Requirement linkage are both confirmed.

#### Scenario: Confirmed materialization serializes successfully

- **GIVEN** a validated ready handoff materializes an exact linked child
- **WHEN** the CLI returns its result
- **THEN** it exits zero with parseable JSON identifying the Requirement and child
- **AND** an exact retry reports that same child without duplicate durable work

### Requirement: Sequential Requirement children can share one integration delivery

Dev Platform SHALL support verified nonterminal child handoff and SHALL combine sequential isolated child results into one requirement-level candidate by default when the children are parts of one delivery outcome. The candidate SHALL be opened as a draft PR once the first verified child is ready and SHALL grow by appending later ready children to that same PR until every mandatory child is present.

#### Scenario: Two children share one publication

- **GIVEN** two linked children have exact verified ready-for-integration receipts
- **WHEN** their parent Requirement is integrated
- **THEN** the candidate combines the exact child results in an isolated worktree and verifies interactions
- **AND** one protected PR and mandatory full CI own final delivery
- **AND** each child remains traceable to its own package, commit and verification receipt

#### Scenario: The shared PR opens before all children finish

- **GIVEN** a Requirement has two or more mandatory children and the first is verified and ready
- **WHEN** the supervisor advances
- **THEN** one draft shared PR exists for the exact candidate before the remaining children complete
- **AND** a later ready child is appended to the same branch and PR rather than creating another delivery

#### Scenario: An incomplete Requirement cannot be delivered

- **GIVEN** the candidate does not yet contain every mandatory child
- **WHEN** ready, merge, queue, auto-merge or terminal reconciliation is attempted
- **THEN** it is refused with the missing children named
- **AND** the Requirement and child statuses stay nonterminal

#### Scenario: A child is not terminal at handoff

- **WHEN** a child becomes ready for shared integration
- **THEN** its Issue and Project status remain nonterminal until the exact shared candidate is merged and reconciled

#### Scenario: Handoff has exact child provenance

- **WHEN** a child is handed off for shared integration
- **THEN** a content-bound receipt identifies its parent Requirement, child Issue, OpenSpec change, exact commit, archived contract and successful verification receipt
- **AND** a changed or ambiguous receipt is rejected before candidate assembly

#### Scenario: Separate publication requires a boundary

- **WHEN** independent delivery or rollout risk requires a child to publish separately
- **THEN** the exception is recorded with its reason and uses the existing protected lifecycle

### Requirement: Shared Requirement publication recovers after main advances

The shared Requirement publisher SHALL preserve exact verified child provenance and produce a new base-bound candidate generation when authoritative main advances before publication. It SHALL NOT rewrite child branches, take over an earlier candidate, or bypass full checks and protected PR authority.

#### Scenario: Unrelated main change is replayed safely

- **GIVEN** a clean prior candidate and exact child receipts based on an older main
- **WHEN** an unrelated protected change advances main before the candidate's first PR
- **THEN** a distinct candidate generation applies the same exact child deltas to current main
- **AND** the prior candidate remains untouched
- **AND** the new candidate must pass full validation and protected publication before terminal status

#### Scenario: Recovery fails closed

- **GIVEN** a changed child head, conflicting patch, occupied generation or mismatched local source contract
- **WHEN** the candidate is resumed or composed
- **THEN** no unrelated worktree is reset, overwritten, force-pushed or published
- **AND** the blocker identifies the exact failed boundary

#### Scenario: Candidate receives its local validation contract

- **GIVEN** the integration checkout uses an ignored `.dev-platform.toml` for source validation
- **WHEN** a candidate worktree is created or resumed
- **THEN** it receives the same-content local contract without changing tracked candidate files
- **AND** validation does not silently fall back to a different operator profile

### Requirement: Requirement child execution uses bounded canonical context

Each internal Requirement child SHALL start or resume from its own materialized managed OpenSpec package, current repository state, and only explicit bounded dependency evidence. The Requirement supervisor SHALL NOT pass the accumulated pre-authoring transcript or unrelated sibling detail as child execution context.

#### Scenario: Child starts with canonical context

- **GIVEN** a linked child has an imported managed package and declared dependencies
- **WHEN** its execution handoff is assembled
- **THEN** the handoff identifies the exact child source and current repository revision
- **AND** it includes only the dependency receipts required for that child
- **AND** it excludes the pre-authoring transcript and unrelated sibling task bodies

#### Scenario: Dependency changes before resume

- **WHEN** a dependency receipt no longer matches canonical state
- **THEN** child execution stops on the stale handoff
- **AND** a fresh bounded handoff can be derived without recreating the child or trusting old transcript content

#### Scenario: Authored parent prose is not a canonical backlink

- **GIVEN** a child Issue describes a Parent Requirement in authored prose
- **WHEN** the managed adapter links or validates that child
- **THEN** it requires an exact canonical `Requirement: owner/repo#N` line and reciprocal parent listing
- **AND** a substring inside `Parent Requirement:` is not accepted as linkage evidence

### Requirement: Explicit Requirement execution reaches terminal delivery

An explicit Execute Requirement request SHALL drive every ready internal child through the existing managed lifecycle and the appropriate single-child or shared integration boundary, stopping only for a consequential decision or external blocker. The supervisor SHALL derive its next action from canonical state rather than persist an independent child queue.

#### Scenario: Ready children are executed in dependency order

- **GIVEN** a Requirement has complete pre-authoring and ready handoffs for sequential children
- **WHEN** execution is requested
- **THEN** each exact child is reused or materialized and bidirectionally linked
- **AND** each child starts or resumes in an isolated managed worktree with only its required predecessor receipt
- **AND** a handoff alone is never reported as terminal delivery

#### Scenario: Parent prose cannot suppress the canonical link

- **GIVEN** an authored child bundle contains `Parent Requirement: owner/repo#N` as prose
- **WHEN** the Requirement handoff is materialized
- **THEN** the generated Issue includes the exact standalone `Requirement: owner/repo#N` backlink before package source evidence is captured
- **AND** the subsequent child start does not require acknowledging an adapter-created source revision

#### Scenario: An interrupted run is resumed

- **GIVEN** a child or shared candidate already exists
- **WHEN** the supervisor repeats Execute Requirement
- **THEN** it derives the current state and resumes the exact child, receipt, candidate or PR without duplication
- **AND** stale or ambiguous evidence blocks the unsafe transition with an actionable diagnostic

#### Scenario: A historical handoff was rebased after delivery

- **GIVEN** a linked child for a handoff's managed change is already canonical or delivered
- **WHEN** pre-authoring refresh changes that handoff's digest
- **THEN** the supervisor reuses the unique exact linked child instead of creating a duplicate Issue
- **AND** multiple children claiming one change fail closed

#### Scenario: A verified ready child stops claiming active writer scope

- **GIVEN** a child has a verified ready receipt at its exact clean committed head
- **WHEN** the supervisor advances to a dependent child
- **THEN** the prior child relinquishes only its own active board writer claim while retaining its worktree, Issue and receipt
- **AND** a dirty worktree, changed head or missing receipt blocks claim release and dependent start

#### Scenario: Terminal completion is authoritative

- **WHEN** all required children have verified ready receipts and their ordinary or shared candidate has merged through protected publication
- **THEN** the supervisor reconciles child and local main state before reporting the Requirement complete
- **AND** a missing child, failed check, unmerged PR or uncertain external state prevents a Done claim

#### Scenario: A direct handoff enters child execution

- **GIVEN** deterministic or bounded-evidence pre-authoring produces a direct handoff
- **WHEN** the supervisor advances
- **THEN** the handoff is materialized and executed as one managed child without ADD or intents

#### Scenario: One child uses ordinary publication

- **GIVEN** exactly one mandatory child is ready
- **WHEN** the supervisor advances after archive
- **THEN** it uses that child's ordinary exact managed PR and terminal reconciliation
- **AND** no shared candidate or special integration exception is required

### Requirement: Requirement board status is derived from terminal authority

The primary Requirement Project card SHALL reflect a recomputable projection of current orchestrator, child and shared-publication evidence. The Project field SHALL NOT become a second independent lifecycle.

#### Scenario: Execution is visible without premature completion

- **GIVEN** a Requirement has one or more linked children in progress or ready for shared integration
- **WHEN** its Project card is reconciled
- **THEN** the card shows a nonterminal execution stage
- **AND** no child receipt or handoff alone makes it Done

#### Scenario: Uncertain evidence fails closed

- **GIVEN** a required source is stale, missing, contradictory or explicitly blocked
- **WHEN** the board projection is computed
- **THEN** it reports blocked or unknown with a reason
- **AND** it does not optimistically write Ready or Done

#### Scenario: Protected publication permits Done

- **GIVEN** every required child is delivered and the exact ordinary child or shared candidate PR is merged with local main reconciled
- **WHEN** the Requirement card is reconciled
- **THEN** it reaches Done idempotently
- **AND** child Issues remain excluded from the primary human-facing view

#### Scenario: Historical delivered parent is retried

- **GIVEN** all linked mandatory children are closed, Done and archived on main
- **WHEN** terminal reconciliation is retried
- **THEN** the parent reaches Done and closes idempotently

### Requirement: Business Requirement completion includes a bounded end-to-end retrospective

Before a non-trivial Business Requirement reaches terminal Done, Dev Platform SHALL require a truthful, fresh retrospective of the complete Requirement-first path: accepted Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery. New meaningful process findings SHALL use the existing friction/process-issue mechanism. A clean run MAY record a concise `none` result. The existing technical child post-task retrospective SHALL remain independently required and SHALL not be duplicated at parent level.

The parent review SHALL inspect meaningful successful manual workarounds, non-default or override actions, manual state changes, recurrences of already open process problems, and observed material drift even when another operator or lifecycle owns the state. `none` requires this bounded factual path review and remains concise on a clean path.

The parent review SHALL use the same mandatory-signal set, dispositions and evidence-gap rules as the task retrospective for signals attributed to the Requirement during pre-authoring and between children, including legacy events attributed by branch or source issue, and SHALL name an unreadable evidence source instead of treating it as clean.

#### Scenario: Significant friction predates children

- **GIVEN** pre-authoring incurred repeated rework or a manual workaround before any child was materialized
- **WHEN** the parent retrospective is performed
- **THEN** the meaningful finding is routed through existing friction evidence and linked to the parent result
- **AND** clean child checkpoints do not erase it

#### Scenario: Cross-child friction survives clean children

- **GIVEN** children each finish cleanly but handoff or decomposition caused duplicate work or conflict between them
- **WHEN** the parent retrospective is performed
- **THEN** the cross-child finding is recorded without fabricating a child failure

#### Scenario: Clean parent and terminal gate

- **WHEN** the full path reveals no new meaningful finding
- **THEN** a concise `none` result suffices
- **AND** missing, stale, ambiguous, or unsupported retrospective evidence blocks parent Done with a recovery action

#### Scenario: Open issue recurs in Requirement delivery

- **GIVEN** a known open process issue is encountered again while delivering a Requirement
- **WHEN** the parent review runs
- **THEN** the recurrence is retained as new occurrence evidence linked to the existing problem
- **AND** the parent does not claim `none` merely because the issue was already known.

#### Scenario: Operator-owned drift is observed

- **WHEN** the agent observes material state drift outside its own ownership during the Requirement path
- **THEN** the review considers it as process evidence regardless of who may repair it.

#### Scenario: Requirement signal is unexplained

- **GIVEN** a workaround event is attributed to the Requirement and not linked or classified
- **WHEN** the parent checkpoint is attempted with `none`
- **THEN** it is refused naming the event.

### Requirement: Every lifecycle stage participates in the shared process learning loop

A new lifecycle stage SHALL either route its meaningful process friction through the existing friction mechanism or make that evidence available to the nearest enclosing retrospective. Specialized reviews MAY contribute evidence but SHALL not introduce a separate improvement backlog or lifecycle.

#### Scenario: New pre-authoring stage detects friction

- **WHEN** a new stage is added before technical child execution
- **THEN** its meaningful friction is directly recorded or guaranteed to reach the parent Requirement retrospective

### Requirement: Business Requirement targets have a supported managed lifecycle

A Business Requirement SHALL enter normal intake or execution only when its target repository can demonstrate the managed OpenSpec child, verification, protected publication and terminal reconciliation path required by that Requirement. Local support requires the target's managed capabilities and required lifecycle entrypoints, in addition to valid Backlog routing and protected publication configuration. Backlog routing labels or operator parameters alone SHALL NOT prove lifecycle support. The check SHALL use target-owned evidence and SHALL fail before creating a new Requirement or beginning execution of an existing one when support is absent or unreadable. A rejection SHALL identify the missing evidence and an available supported route without silently retargeting or manually closing the Requirement.

#### Scenario: Unsupported operator repository has routing but no managed lifecycle

- **GIVEN** a target repository can supply a Backlog repository, project label and priority
- **AND** it lacks the managed child and publication lifecycle required for Requirement execution
- **WHEN** a local or connected actor attempts Requirement fixation or execution
- **THEN** the operation stops before normal Requirement progress
- **AND** explains the missing lifecycle support and a supported target checkout or workflow route

#### Scenario: Managed target proceeds

- **GIVEN** a target checkout proves its configured managed OpenSpec and publication lifecycle
- **WHEN** a Requirement is fixed or started for that target
- **THEN** normal Requirement routing and execution remain available

#### Scenario: Explicit operator-managed downstream opt-in proceeds

- **GIVEN** an operator-managed downstream target has explicit integration evidence and the required managed entrypoints
- **AND** its Backlog routing parameters derive from its target checkout configuration
- **WHEN** local or connected Requirement intake checks that target
- **THEN** the target is supported without requiring a committed machine-local operator configuration

### Requirement: Requirement terminal state requires target delivery proof

Requirement terminal reconciliation SHALL require a supported target lifecycle and the existing exact linked-child, archived verification and merged delivery evidence. A manually closed Issue, Project Done field, or empty child set SHALL NOT substitute for that proof.

#### Scenario: Target lacks a terminal path

- **GIVEN** a Requirement Issue appears complete or its work was delivered outside managed execution
- **WHEN** terminal reconciliation cannot prove the target's supported managed lifecycle and exact delivered children
- **THEN** it refuses parent Done and Issue closure
- **AND** reports the missing terminal proof

### Requirement: Same-context compaction is considered at semantic work boundaries

Dev Platform SHALL support bounded same-context compaction opportunities at semantic transitions in live work rather than treating context-window fullness as the sole trigger. The initial capability SHALL keep the opportunity set small and inspectable, such as completion of a bounded plan/subtask or transition into a distinct verification phase.

#### Scenario: Subtask completes with substantial work remaining

- **GIVEN** a live managed run completes a bounded subtask
- **AND** meaningful downstream work remains in the same context
- **WHEN** the workflow reaches a configured semantic compaction opportunity
- **THEN** the platform may evaluate whether compaction is beneficial
- **AND** it does not compact merely because the opportunity exists

#### Scenario: No semantic boundary is reached

- **WHEN** a live run is still in the middle of one bounded reasoning/implementation step
- **THEN** the platform does not force semantic compaction solely from a fixed context-percentage threshold

### Requirement: Same-context compaction uses an inspectable economic gate

At a semantic compaction opportunity, the platform SHALL use a simple inspectable gate that considers available evidence about expected future replay avoided and compaction/rebuild overhead or risk. Compaction SHALL occur only when the gate passes. V1 SHALL NOT require a learned optimizer.

Before evaluating compaction benefit, the advisory workflow SHALL check whether safely reducible repeated instructions, eager loading of rarely needed tool/capability definitions, or prompt-boundary instability account for the hot payload. It SHALL evaluate compaction against the remaining live-history cost and SHALL NOT grow this check into a general prompt optimizer.

#### Scenario: Cheaper static reduction explains the payload

- **GIVEN** a semantic opportunity is reached
- **AND** repeated instructions or unneeded eager capability definitions account for the apparent replay cost
- **WHEN** the advisory gate evaluates the opportunity
- **THEN** it records the cheaper reduction opportunity and evaluates only residual compaction benefit
- **AND** it may keep the current context when that benefit is no longer material

#### Scenario: Expected replay benefit is not material

- **GIVEN** a semantic opportunity is reached
- **BUT** little future replay is expected or compact overhead is not justified
- **WHEN** the economic gate evaluates the opportunity
- **THEN** the workflow keeps the current context
- **AND** records an inspectable no-compact reason where dogfood evidence is enabled

#### Scenario: Expected replay benefit materially exceeds overhead

- **GIVEN** a semantic opportunity is reached
- **AND** available evidence indicates substantial future replay would otherwise continue
- **WHEN** the economic gate passes
- **THEN** the runtime may compact the same live context
- **AND** the decision remains distinguishable from a durable handoff

### Requirement: Same-context compaction preserves continuation truth

A compacted continuation SHALL preserve the exact managed task/OpenSpec identity, verified facts with canonical evidence references, unresolved assumptions, blockers and next intent needed to continue safely. Large exact evidence MAY remain cold through valid observation handles. Compact prose SHALL NOT override repository, OpenSpec, test or other canonical evidence.

#### Scenario: Compacted continuation resumes safely

- **GIVEN** same-context compaction succeeded
- **WHEN** work resumes
- **THEN** the agent can identify the same managed task and canonical contract
- **AND** verified facts remain distinguishable from unresolved assumptions
- **AND** referenced cold evidence can be recalled exactly when needed

#### Scenario: Referenced evidence is stale or missing

- **GIVEN** a compact continuation references evidence that can no longer be resolved or whose identity changed
- **WHEN** the continuation attempts to rely on that evidence
- **THEN** the missing/stale reference is surfaced
- **AND** the compact prose is not treated as proof of the unavailable evidence

### Requirement: Same-context compaction dogfood evidence is truthful

Initial compaction rollout SHALL remain advisory/dogfood and SHALL record bounded opportunity/decision evidence without inventing token savings. Deterministic before/after payload measures and observed replay MAY be recorded; token/cache/request savings SHALL be claimed only from exact supported runtime evidence.

#### Scenario: Runtime provides no exact cache-token evidence

- **WHEN** compaction reduces deterministic active payload size but the runtime exposes no canonical cache-token measurement
- **THEN** the deterministic reduction is recorded
- **AND** token/cache savings remain unknown rather than estimated

### Requirement: An own stale ready receipt is superseded on proven head advancement

When Requirement execution records a ready-for-integration receipt for a child and a different receipt already exists at that location, the platform SHALL replace it only when the existing receipt is valid, carries the identical Requirement, child Issue, change and source branch, and its recorded head is a strict ancestor of the new head in the child's repository. Any other existing receipt SHALL continue to block with an actionable diagnostic. A supersession SHALL be reported in the execution result.

#### Scenario: A failed attempt left the lifecycle's own receipt for an older head
- **GIVEN** a valid ready receipt for the same Requirement, child, change and branch records an ancestor of the current child head
- **WHEN** the supervisor advances again
- **THEN** the receipt is replaced by the receipt for the current head without manual cleanup
- **AND** the result reports the superseded head

#### Scenario: The existing receipt is foreign or ambiguous
- **GIVEN** an existing receipt with a different identity, an unreadable or invalid payload, a head that is not a strict ancestor of the new head, or the same head with different content
- **WHEN** the supervisor writes the ready receipt
- **THEN** the write is refused and the lifecycle stays blocked

### Requirement: Started Requirement is claimed on its card before preparation continues

When Requirement execution starts, the primary Requirement Project card SHALL be projected to its existing nonterminal status as soon as pre-authoring state is durably initialised, and again at the entry of every resume, before duplicate checks, evidence gathering or child materialisation. The claim follows Requirement validation and the check that durable pre-authoring state exists, so an invalid or unsupported Requirement is not claimed, and it SHALL NOT rewrite a terminal `Done` card. The platform SHALL NOT add a new status for this interval, and no error after the durable start SHALL write or leave a free-looking `Ready` projection by its own action.

#### Scenario: Card is claimed before slow preparation

- **GIVEN** a Requirement card shows `Ready`
- **WHEN** `requirement_intake.py start` initialises its pre-authoring state
- **THEN** the card shows `In progress` before any later pre-authoring or GitHub-dependent step runs
- **AND** a second agent reading the card during the first agent's preparation sees it as occupied

#### Scenario: Restart continues instead of creating parallel ownership

- **GIVEN** a Requirement has durable pre-authoring state
- **WHEN** `start` or `execute_requirement.py advance` is run again
- **THEN** the existing work is continued and the card reconciliation is idempotent
- **AND** a card still showing `Ready` is repaired to `In progress` at entry

#### Scenario: Failure after durable start does not free the card

- **GIVEN** the Requirement has started and its state is durable
- **WHEN** the card reconciliation or a later step fails
- **THEN** the failure is reported, the state is retained and a rerun converges
- **AND** the platform does not write `Ready`

### Requirement: Verified technical child project routing

Dev Platform SHALL derive technical-child routing from the exact parent Requirement's single `project:*` label and Backlog repository together with the committed target `[development_backlog]` configuration, SHALL reject any contradiction, missing or ambiguous routing input before an Issue is created, and SHALL report materialization success only after read-back proves the child's exact `project:*` label, `type:internal-change` label and parent link. The platform SHALL NOT silently relabel a contradictory child.

#### Scenario: Consistent routing

- **WHEN** the parent Requirement label, its Backlog repository and the committed configuration identify the same project
- **THEN** the child is created or exactly reused with that `project:*` label
- **AND** success is reported only after read-back shows `project:*`, `type:internal-change` and the parent link

#### Scenario: Conflicting routing is rejected before publication

- **WHEN** the committed `project_label` or Backlog repository differs from the parent Requirement's
- **THEN** materialization fails naming the Requirement, expected and found values
- **AND** no Issue is created

#### Scenario: Missing or ambiguous routing input

- **WHEN** the parent has no `project:*` label or more than one, or required target configuration or the Backlog label is absent
- **THEN** materialization fails naming the missing or ambiguous input and creates nothing

#### Scenario: Read-back mismatch is not success

- **WHEN** the created or reused child lacks the expected `project:*` label, `type:internal-change` or the parent back-reference on read-back
- **THEN** materialization reports failure naming the child and no success result is produced

#### Scenario: Existing mislabeled child is a visible error

- **GIVEN** an exact-handoff child already exists with a contradictory or absent `project:*` label
- **WHEN** the handoff is retried
- **THEN** materialization fails with the child reference, expected and found labels and manual repair guidance
- **AND** no `project:*` label is added, removed or replaced

#### Scenario: Retry completes only the deterministic internal-change label

- **GIVEN** an exact-handoff child with the correct `project:*` label but missing `type:internal-change`
- **WHEN** the handoff is retried
- **THEN** the missing `type:internal-change` label is added once and re-verified before success
