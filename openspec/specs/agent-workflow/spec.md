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

Before a non-trivial Business Requirement reaches terminal Done, Dev Platform SHALL require a truthful, fresh retrospective of the complete Requirement-first path: accepted Requirement, pre-authoring, handoff/decomposition, mandatory children, and delivery. A clean run MAY record a concise `none` result.

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

A Business Requirement SHALL enter normal intake or execution only when its target repository can demonstrate the managed OpenSpec child, verification, protected publication and terminal reconciliation path required by that Requirement. Local support requires the target's managed capabilities and required lifecycle entrypoints, in addition to valid Backlog routing and protected publication configuration.

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

#### Scenario: Integration main was not fast-forwarded

- **GIVEN** a child's archived change with its verification receipt is merged on remote main
- **AND** the local integration main has not been fast-forwarded to it
- **WHEN** terminal reconciliation runs in the integration checkout
- **THEN** it proves that child's delivery from the fetched remote main commit
- **AND** it leaves the local integration main and working tree unchanged

#### Scenario: Remote main lacks the archive

- **WHEN** the fetched remote main commit has no archived change with a verification receipt for a child, even though the local checkout has one
- **THEN** terminal reconciliation refuses, naming that child

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

When Requirement execution records a ready-for-integration receipt for a child and a different receipt already exists at that location, the platform SHALL replace it only when the existing receipt is valid, carries the identical Requirement, child Issue, change and source branch, and its recorded head is a strict ancestor of the new head in the child's repository. Any other existing receipt SHALL continue to block with an actionable diagnostic.

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

When Requirement execution starts, the primary Requirement Project card SHALL be projected to its existing nonterminal status as soon as pre-authoring state is durably initialised, and again at the entry of every resume, before duplicate checks, evidence gathering or child materialisation. The claim follows Requirement validation and the check that durable pre-authoring state exists, so an invalid or unsupported Requirement is not claimed, and it SHALL NOT rewrite a terminal `Done` card.

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

Dev Platform SHALL derive technical-child routing from the exact parent Requirement's single `project:*` label and Backlog repository together with the committed target `[development_backlog]` configuration, SHALL reject any contradiction, missing or ambiguous routing input before an Issue is created, and SHALL report materialization success only after read-back proves the child's exact `project:*` label, `type:internal-change` label and parent link.

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

### Requirement: ADD preparation separates product contract from system delta

When preparing an Architecture Design Delta, the agent SHALL classify each candidate against the accepted Business Requirement, accepted OpenSpec and active deltas, project context, code/tests and bounded evidence, and SHALL place it in exactly one destination: an already accepted product contract, an existing authoritative technical contract, a real ADD delta, OpenSpec-level implementation detail, or an open product question.

#### Scenario: Detailed Business Requirement

- **WHEN** the Business Requirement already fixes several user-facing behaviours and rules
- **THEN** the ADD lists only the system-level changes they imply relative to the current system
- **AND** the fixed behaviours are not asked of the human again

#### Scenario: Real system delta

- **WHEN** an accepted behaviour requires a changed event contract, responsibility boundary, data ownership or invariant not set by the sources
- **THEN** the ADD states the difference from the current accepted state, the reason and the impact

#### Scenario: Decision already determined by evidence

- **WHEN** an authoritative existing contract determines the choice
- **THEN** the ADD references it as preserved and asks no human question

#### Scenario: Product uncertainty

- **WHEN** a material product decision is missing for correct development
- **THEN** it is shown as a clarification of the Business Requirement
- **AND** the agent neither decides it nor presents it among architectural alternatives

### Requirement: ADD is presented to the human through one standard read-only projection

Whenever the process shows an ADD to a human for a decision or approval, the presentation SHALL be the output of `add_intents.py render-add` for the current ADD document.

#### Scenario: Open consequential alternative

- **WHEN** the ADD has an open architectural choice with options and a recommendation
- **THEN** the projection shows the options, trade-offs, recommendation and exact subject of decision in state «нужны решения»
- **AND** `approve-add` still refuses until it is resolved

#### Scenario: Product clarification

- **WHEN** the ADD records an open choice of kind product
- **THEN** the projection shows it under a separate heading as a clarification of the Business Requirement

#### Scenario: ADD edited after approval

- **WHEN** the material content of an approved ADD changes
- **THEN** the projection shows «требует актуализации» and the earlier approval is not presented as current
- **AND** after re-approval through the existing mechanism it shows «утверждён» for the new content

#### Scenario: Same ADD from different routes

- **WHEN** two agents or projects render the same ADD content
- **THEN** the output is identical in structure and wording of fixed labels

#### Scenario: No new process machinery

- **WHEN** the standard is delivered
- **THEN** no lifecycle stage, approval gate, semantic validator, decision registry, stored report, separate interface or per-project setting exists beyond the read-only command and the existing ADD fields
- **AND** no claim is made that structural checks prove the design is correct

### Requirement: Requirement retrospective covers delivery by quick PRs

The Requirement retrospective checkpoint SHALL accept a Requirement with no linked managed children when the operator names the merged quick pull requests that delivered it, and SHALL record them in the receipt, which is then checked like any other Requirement retrospective. Each named pull request SHALL be merged. Named quick pull requests MAY accompany managed children for a Requirement delivered partly by quick work.

#### Scenario: Requirement delivered only by quick PRs

- **GIVEN** a Requirement with an empty children block delivered by merged quick PRs
- **WHEN** `requirement_retrospective.py checkpoint --quick-pr owner/repo#N ...` runs
- **THEN** the receipt is recorded with the quick PRs and `check` reports it ready

#### Scenario: No children and no quick PRs

- **WHEN** the checkpoint runs for a Requirement with an empty children block and no `--quick-pr`
- **THEN** it is refused naming `--quick-pr`

#### Scenario: Named PR is not merged

- **WHEN** a named quick PR is not merged
- **THEN** the checkpoint stops naming that PR and records nothing

### Requirement: Execute Requirement refuses advance after a merged composition

When a Requirement's composition pull request from its integration branch into `main` is already merged, `execute_requirement.py advance` SHALL stop before it creates, fetches or pushes the integration branch. The refusal SHALL name the merged pull request, state that advancing would recreate the integration branch and break the post-merge jobs, and name the supported next steps: the coordinator's post-merge jobs for that pull request and the read-only publication status.

#### Scenario: Composition already merged

- **GIVEN** the composition PR #N of `requirement/BR-R` is merged and the branch was deleted
- **WHEN** `advance` runs for the Requirement
- **THEN** it fails naming PR #N and the post-merge job and status commands
- **AND** no `requirement/BR-R` branch is created or pushed

#### Scenario: Composition still open

- **WHEN** the composition PR is open or does not exist yet
- **THEN** advance proceeds as before

#### Scenario: Inventory unavailable

- **WHEN** the pull request list for the integration branch cannot be read
- **THEN** advance fails naming the unavailable inventory and touches no branch

### Requirement: Requirement advance resolves handoff, bundle and child by one key

`execute_requirement.py advance` SHALL resolve a handoff's authored bundle by the handoff id: the bundle directory named after it, or the single bundle whose manifest declares that handoff. The bundle's `change` SHALL name the managed change. A handoff whose bundle is ambiguous or malformed SHALL stop naming the bundles involved.

#### Scenario: Intent and change named differently

- **GIVEN** handoff `I1` whose child was materialized as change `object-client-contract` from bundle `bundles/object-client-contract` declaring `"handoff": "I1"`
- **AND** the handoff was refreshed after materialization
- **WHEN** advance runs
- **THEN** handoff `I1` maps to that child and advance continues without a historical-child error

#### Scenario: Mismatched names

- **GIVEN** the same refreshed handoff and a bundle `bundles/object-client-contract` without a handoff declaration
- **WHEN** advance runs
- **THEN** it fails naming handoff `I1`, the linked child and change `object-client-contract`, and the bundle naming rule

#### Scenario: Two bundles claim one handoff

- **WHEN** two bundle manifests declare the same handoff
- **THEN** advance stops naming both bundles

### Requirement: A newly created Business Requirement carries configured project and priority labels

A newly created Requirement SHALL carry exactly one `project:*` label and exactly one `priority:*` label resolved from the target repository's existing `[development_backlog]` configuration: `project_label`, and the explicitly requested priority or `default_priority`. No separate routing source or default for these Requirement labels SHALL be introduced.

#### Scenario: Requirement labels come from the target configuration

- **WHEN** a Requirement is created for a target repository
- **THEN** it carries exactly one `project:*` label from `project_label` and exactly one `priority:*` label from the explicitly requested priority or `default_priority`
- **AND** no separate routing source or default is used

### Requirement: Business Requirement creation routing fails closed and is read back

Missing or conflicting routing of a newly created Requirement SHALL fail closed, and creation of the Requirement SHALL be reported successful only after a read-back verifies its `project:*` and `priority:*` labels.

#### Scenario: Routing missing or conflicting

- **WHEN** the routing for a newly created Requirement is missing or conflicting
- **THEN** creation fails closed

#### Scenario: Labels read back

- **WHEN** a Requirement has been created
- **THEN** creation is reported successful only after a read-back verifies its `project:*` and `priority:*` labels

### Requirement: Business Requirement retrospective findings use the friction mechanism

New meaningful process findings of the Business Requirement retrospective SHALL use the existing friction/process-issue mechanism.

#### Scenario: New finding in the Requirement retrospective

- **WHEN** the Business Requirement retrospective finds a new meaningful process finding
- **THEN** the finding is recorded through the existing friction/process-issue mechanism

### Requirement: Technical child post-task retrospective stays independent of the parent retrospective

The existing technical child post-task retrospective SHALL remain independently required and SHALL not be duplicated at parent level.

#### Scenario: Child and parent retrospectives

- **WHEN** a Business Requirement with technical children is retrospected
- **THEN** each technical child post-task retrospective is still required independently
- **AND** it is not duplicated at parent level

### Requirement: Parent Requirement review inspects meaningful process signals

The parent Business Requirement review SHALL inspect meaningful successful manual workarounds, non-default or override actions, manual state changes, recurrences of already open process problems, and observed material drift even when another operator or lifecycle owns the state. A `none` result of the parent review requires this bounded factual path review and remains concise on a clean path.

#### Scenario: Signals owned by another operator

- **WHEN** the parent review runs and a manual state change or observed material drift is owned by another operator or lifecycle
- **THEN** the parent review still inspects it

#### Scenario: Clean path

- **WHEN** the bounded factual path review finds nothing
- **THEN** a concise `none` result is recorded

### Requirement: Parent Requirement review applies the task retrospective signal rules

The parent Business Requirement review SHALL use the same mandatory-signal set, dispositions and evidence-gap rules as the task retrospective for signals attributed to the Requirement during pre-authoring and between children, including legacy events attributed by branch or source issue, and SHALL name an unreadable evidence source instead of treating it as clean.

#### Scenario: Legacy event attributed by branch

- **WHEN** a legacy event is attributed to the Requirement by branch or source issue
- **THEN** the parent review applies the task retrospective mandatory-signal set, dispositions and evidence-gap rules to it

#### Scenario: Unreadable evidence source

- **WHEN** an evidence source for the parent review cannot be read
- **THEN** the parent review names that source
- **AND** it is not treated as clean

### Requirement: Backlog routing alone does not prove Requirement target lifecycle support

Backlog routing labels or operator parameters alone SHALL NOT prove lifecycle support of a Business Requirement target repository.

#### Scenario: Only routing labels present

- **WHEN** a target repository has Backlog routing labels or operator parameters but no other lifecycle evidence
- **THEN** its managed lifecycle support is not considered proven

### Requirement: Requirement target lifecycle support check fails before creation or execution

The Business Requirement target lifecycle support check SHALL use target-owned evidence and SHALL fail before creating a new Requirement or beginning execution of an existing one when support is absent or unreadable.

#### Scenario: Support absent or unreadable

- **WHEN** the target-owned lifecycle support evidence is absent or unreadable
- **THEN** the check fails before a new Requirement is created or execution of an existing one begins

### Requirement: Unsupported Requirement target rejection names evidence and a supported route

A rejection of a Business Requirement target without supported managed lifecycle SHALL identify the missing evidence and an available supported route without silently retargeting or manually closing the Requirement.

#### Scenario: Target rejected

- **WHEN** a Business Requirement target is rejected for missing lifecycle support
- **THEN** the rejection identifies the missing evidence and an available supported route
- **AND** the Requirement is neither silently retargeted nor manually closed

### Requirement: Requirement terminal reconciliation reads verification from fetched remote main

The archived verification evidence for Requirement terminal reconciliation SHALL be read from the tree of a freshly fetched remote main commit, not from the integration checkout, so reconciliation neither depends on nor performs a fast-forward of the local integration main; a failed fetch SHALL stop reconciliation.

#### Scenario: Verification read from remote main

- **WHEN** Requirement terminal reconciliation reads the archived verification evidence
- **THEN** it reads it from the tree of a freshly fetched remote main commit, not from the integration checkout
- **AND** the local integration main is not fast-forwarded

#### Scenario: Fetch fails

- **WHEN** the fetch of remote main fails
- **THEN** reconciliation stops

### Requirement: Compaction advisory checks reducible hot payload before compaction benefit

Before evaluating same-context compaction benefit, the advisory workflow SHALL check whether safely reducible repeated instructions, eager loading of rarely needed tool/capability definitions, or prompt-boundary instability account for the hot payload. The advisory workflow SHALL evaluate compaction against the remaining live-history cost and SHALL NOT grow this check into a general prompt optimizer.

#### Scenario: Hot payload from reducible instructions

- **WHEN** the advisory workflow is about to evaluate compaction benefit
- **THEN** it first checks whether repeated instructions, eager tool/capability definitions or prompt-boundary instability account for the hot payload
- **AND** it evaluates compaction against the remaining live-history cost without becoming a general prompt optimizer

### Requirement: Ready receipt supersession is reported in the execution result

A supersession of an existing ready-for-integration receipt during Requirement execution SHALL be reported in the execution result.

#### Scenario: Receipt superseded

- **WHEN** Requirement execution supersedes an existing ready-for-integration receipt
- **THEN** the execution result reports the supersession

### Requirement: Started Requirement claim adds no status and leaves no free-looking Ready

The platform SHALL NOT add a new status for the interval in which a started Requirement is claimed on its Project card before preparation continues, and no error after the durable start of Requirement execution SHALL write or leave a free-looking `Ready` projection by its own action.

#### Scenario: No new status

- **WHEN** a started Requirement is claimed on its card
- **THEN** the card uses an existing nonterminal status and no new status is added

#### Scenario: Error after durable start

- **GIVEN** Requirement execution has started durably
- **WHEN** a later error occurs
- **THEN** the error path does not by its own action write or leave a free-looking `Ready` projection

### Requirement: A contradictory technical child is not silently relabeled

The platform SHALL NOT silently relabel a contradictory technical child.

#### Scenario: Child labels contradict parent routing

- **WHEN** a technical child's labels contradict its derived routing
- **THEN** the platform does not silently relabel the child

### Requirement: Only material system-level changes appear as ADD deltas

Only a new or changed material system-level contract, boundary, storage, data ownership, invariant, security concern or non-functional behavior relative to the current accepted state SHALL appear as a `new` or `changed` ADD delta.

#### Scenario: Material system-level change

- **WHEN** a candidate is a new or changed material system-level contract, boundary, storage, data ownership, invariant, security concern or non-functional behavior relative to the current accepted state
- **THEN** it may appear as a `new` or `changed` ADD delta

#### Scenario: Other candidate

- **WHEN** a candidate is not such a material system-level change
- **THEN** it does not appear as a `new` or `changed` ADD delta

### Requirement: Business Requirement product behaviour is a constraint in ADD preparation

Product behaviour already defined by the Business Requirement SHALL be used as a constraint in ADD preparation and SHALL NOT be re-presented as an architectural alternative requiring approval.

#### Scenario: Product behaviour already defined

- **WHEN** an ADD candidate is product behaviour already defined by the Business Requirement
- **THEN** it is used as a constraint
- **AND** it is not presented as an architectural alternative requiring approval

### Requirement: Existing technical contracts are referenced as preserved in an ADD

An existing technical contract SHALL be referenced in an ADD as preserved and SHALL NOT be re-offered as a choice.

#### Scenario: Existing technical contract

- **WHEN** an ADD candidate is an existing technical contract
- **THEN** the ADD references it as preserved
- **AND** it is not re-offered as a choice

### Requirement: Code naming and sequencing remain OpenSpec detail

Naming of functions, handlers, files or code sequencing SHALL remain OpenSpec detail.

#### Scenario: Naming candidate

- **WHEN** an ADD candidate concerns naming of functions, handlers, files or code sequencing
- **THEN** it remains OpenSpec detail

### Requirement: A missing product decision is a Business Requirement clarification

A material missing product decision SHALL be marked as a clarification of the Business Requirement, not decided in the ADD.

#### Scenario: Product decision missing

- **WHEN** ADD preparation finds a material missing product decision
- **THEN** it is marked as a clarification of the Business Requirement
- **AND** it is not decided in the ADD

### Requirement: ADD candidate classification is evidence-first agent judgement

The classification of ADD candidates SHALL be the agent's evidence-first judgement and SHALL NOT be a keyword or category gate or require an LLM judge.

#### Scenario: Classifying candidates

- **WHEN** the agent classifies ADD candidates
- **THEN** the classification is its evidence-first judgement
- **AND** no keyword or category gate and no LLM judge is required

### Requirement: A bounded change without a design delta skips ADD

A bounded change without a useful design delta SHALL continue to skip ADD and intents.

#### Scenario: No useful design delta

- **WHEN** a bounded change has no useful design delta
- **THEN** ADD and intents are skipped

### Requirement: The render-add ADD presentation message has a fixed header and delta sections

The output of `add_intents.py render-add` for the current ADD document SHALL be a Russian Markdown message with the Business Requirement reference, target repository, ADD identity and content revision with a state derived from existing facts; a 2–4 sentence summary; a table of only the material `new`/`changed` deltas; what is preserved.

#### Scenario: ADD rendered

- **WHEN** `add_intents.py render-add` renders the current ADD document
- **THEN** the output is a Russian Markdown message with the Business Requirement reference, target repository, ADD identity and content revision with a derived state
- **AND** it has a 2–4 sentence summary, a table of only the material `new`/`changed` deltas and what is preserved

### Requirement: The render-add ADD presentation message has question and risk sections

The Russian Markdown message output by `add_intents.py render-add` for the current ADD document SHALL also contain questions that need the human with options, trade-offs and the recommendation where recorded, with product clarifications shown separately; and risks with one unambiguous next action.

#### Scenario: ADD with questions and risks

- **WHEN** `add_intents.py render-add` renders an ADD with questions for the human and risks
- **THEN** the message shows the questions with options, trade-offs and the recommendation where recorded, with product clarifications shown separately
- **AND** it shows the risks with one unambiguous next action

### Requirement: Empty sections are omitted from the render-add ADD presentation

Sections of the `add_intents.py render-add` ADD presentation without content SHALL be omitted.

#### Scenario: Section without content

- **WHEN** a section of the ADD presentation has no content
- **THEN** the section is omitted

### Requirement: The render-add ADD state is approved only with a current proven approval

The state of the `add_intents.py render-add` ADD presentation SHALL be «утверждён» only when the ADD is structurally valid, approved, its approval digest matches the current content and its freshness is proven; an approval that is stale or whose freshness cannot be proven SHALL render as «требует актуализации».

#### Scenario: Current approval

- **WHEN** the ADD is structurally valid, approved, its digest matches and its freshness is proven
- **THEN** the state is «утверждён»

#### Scenario: Stale or unprovable approval

- **WHEN** the ADD approval is stale or its freshness cannot be proven
- **THEN** the state renders as «требует актуализации»

### Requirement: The render-add ADD state otherwise follows open choices, content and freshness

In the `add_intents.py render-add` ADD presentation, an ADD with an open choice or unresolved contradiction SHALL be «нужны решения»; an ADD without elements or choices SHALL be «предложение»; otherwise, when neither «утверждён» nor a stale or unprovable approval applies, it SHALL be «готов к утверждению» only when its freshness is proven and «требует актуализации» when it is not.

#### Scenario: Open choice

- **WHEN** the ADD has an open choice or unresolved contradiction
- **THEN** the state is «нужны решения»

#### Scenario: Empty ADD

- **WHEN** the ADD has no elements or choices
- **THEN** the state is «предложение»

#### Scenario: Other ADD

- **WHEN** none of the other states applies
- **THEN** the state is «готов к утверждению» when freshness is proven and «требует актуализации» when it is not

### Requirement: The render-add ADD projection is read-only and fails on invalid ADDs

The `add_intents.py render-add` ADD projection SHALL be read-only, SHALL write no file or status, SHALL NOT approve, and SHALL fail explicitly on an ADD that is structurally invalid for any reason other than a stale approval digest.

#### Scenario: Projection runs

- **WHEN** the projection renders an ADD
- **THEN** it writes no file or status and does not approve

#### Scenario: Structurally invalid ADD

- **WHEN** the ADD is structurally invalid for a reason other than a stale approval digest
- **THEN** the projection fails explicitly

### Requirement: The render-add ADD projection content is independent of the invoker

The content of the `add_intents.py render-add` ADD projection SHALL NOT depend on the agent or project that invokes the projection.

#### Scenario: Different invokers

- **WHEN** different agents or projects invoke the projection for the same ADD
- **THEN** the content does not depend on the invoking agent or project

### Requirement: Presenting the render-add ADD projection adds no process machinery

Presenting the `add_intents.py render-add` ADD projection SHALL add no mandatory human stop, no new approval mechanism and no project configuration.

#### Scenario: Projection presented

- **WHEN** the projection is presented to a human
- **THEN** no mandatory human stop, new approval mechanism or project configuration is added

### Requirement: Requirement retrospective refuses a Requirement without children or quick PRs

A Requirement with neither linked managed children nor named quick pull requests SHALL be refused by the Requirement retrospective checkpoint with the next action.

#### Scenario: Nothing delivered it

- **WHEN** the Requirement retrospective checkpoint runs for a Requirement with neither linked managed children nor named quick pull requests
- **THEN** it is refused with the next action

### Requirement: Execute Requirement advance stops on an unreadable integration branch inventory

When the pull request inventory of a Requirement's integration branch cannot be read, `execute_requirement.py advance` SHALL stop naming that unreadable inventory instead of assuming no composition exists.

#### Scenario: Inventory unreadable

- **WHEN** the pull request inventory of the integration branch cannot be read
- **THEN** advance stops naming the unreadable inventory
- **AND** it does not assume that no composition exists

### Requirement: Requirement advance fails on an unmapped nonterminal linked child

When a linked child that is not terminal maps to no current handoff, `execute_requirement.py advance` SHALL fail naming that child, its change and the handoffs left unmapped, with the bundle naming rule as the next action.

#### Scenario: Nonterminal child without handoff

- **WHEN** a nonterminal linked child maps to no current handoff
- **THEN** advance fails naming the child, its change and the unmapped handoffs
- **AND** the bundle naming rule is given as the next action

### Requirement: An authored bundle can be checked before advance

`orchestrate_pre_authoring.py check-bundle` SHALL run the bundle validation advance uses on every authored bundle of a complete pre-authoring state and SHALL fail naming the OpenSpec error. The check SHALL be optional: advance SHALL validate as before and SHALL NOT read or reuse any check result. status SHALL only name the command.

#### Scenario: A bundle lost a MODIFIED scenario

- **GIVEN** a complete pre-authoring state whose bundle MODIFIES a requirement without one of its scenarios
- **WHEN** `check-bundle` runs
- **THEN** it fails naming the requirement and the missing scenario
- **AND** no child Issue exists

#### Scenario: A correct bundle

- **WHEN** `check-bundle` runs on a valid bundle
- **THEN** it reports the bundle valid
- **AND** advance then materializes the child exactly as before
