## MODIFIED Requirements

### Requirement: Incomplete managed-start recovery is fenced to exact task identity

When a managed start finds transaction state without matching canonical OpenSpec provenance, the platform SHALL treat this as bounded incomplete creation state for that exact task and MAY recover it.

#### Scenario: Exact partial task is recovered without touching a sibling

- **GIVEN** task A's transaction names a worktree/branch that is only partially created
- **AND** an unrelated sibling task's worktree is separately dirty
- **WHEN** task A retries its managed start
- **THEN** only task A's exact worktree/branch/board entry is inspected and, if safe, recovered
- **AND** the sibling task's worktree and board entry are left untouched

#### Scenario: Board lookup is fenced to exact task identity

- **GIVEN** the agent board contains a stale entry for an unrelated task
- **WHEN** recovery resolves the board entry for the current task's transaction
- **THEN** it matches only the exact `(worktree, branch)` identity recorded in the transaction
- **AND** more than one matching board entry fails recovery closed as ambiguous rather than picking one

#### Scenario: Unsafe partial state blocks automatic recovery

- **WHEN** the candidate worktree named by the transaction has commits not reachable from `main`, dirty paths the task does not own, or task-local state naming a different source issue or change
- **THEN** recovery fails closed with an actionable diagnostic
- **AND** no worktree, branch or board mutation occurs

#### Scenario: Non-canonical path is never deleted as retry debris

- **WHEN** the transaction names a path that is not an exact registered Git worktree
- **THEN** recovery leaves that path untouched and reports that ownership could not be proven
- **AND** does not guess that the path is safe retry debris

### Requirement: Fresh non-trivial execution enters managed intake before implementation

When a user asks to execute a fresh non-trivial change, the platform SHALL create or reuse a Business Requirement and run requirement-first pre-authoring before implementation. Each resulting internal managed OpenSpec child SHALL be linked to the parent Requirement, started through the standard managed lifecycle, and implemented against its materialized canonical OpenSpec. An explicitly requested direct technical managed task remains an exception.

#### Scenario: User asks Codex to implement a fresh non-trivial change

- **WHEN** the user asks to implement, fix, build, or otherwise execute a material change without supplying a technical managed task
- **THEN** the agent creates or reuses a Business Requirement, starts pre-authoring, authors and links its internal technical child or children, and starts those children
- **AND** implementation begins only after canonical OpenSpec materialization and required preflight

#### Scenario: Existing managed task already represents the execution request

- **WHEN** the user supplies an existing `type:requirement` Issue for execution
- **THEN** the platform starts or resumes that Requirement's pre-authoring state without creating a duplicate Requirement
- **AND** an explicitly supplied existing technical managed task instead follows the direct managed start/resume contract

### Requirement: Quick work escalates to managed intake before becoming a material OpenSpec change

Quick execution SHALL remain available for small bounded work, including a repair that restores unambiguously accepted behavior when the user requests execution now.

#### Scenario: Directly requested bounded regression repair

- **GIVEN** an accepted spec or durable contract unambiguously establishes the expected behavior
- **AND** a small defect violates that behavior
- **WHEN** the user requests the repair now
- **THEN** the repair may use the existing quick lifecycle without a new Requirement or OpenSpec delta
- **AND** it records proportionate regression evidence and passes applicable safety and publication gates

#### Scenario: Representative quick fix stays bounded

- **GIVEN** a small clear change needs no full OpenSpec contract
- **WHEN** the user requests immediate execution
- **THEN** the quick lifecycle may execute without a Backlog Issue or ceremonial OpenSpec

#### Scenario: Reasonable regression seam exists

- **GIVEN** a bounded quick regression repair has a reasonable test seam
- **WHEN** the repair is completed
- **THEN** a check demonstrated the defect before the repair and passes after it
- **AND** the original failure path is rerun

#### Scenario: No reasonable regression seam exists

- **GIVEN** no reasonable automated test seam exists for a bounded repair
- **WHEN** the repair is completed
- **THEN** the limitation and the actual alternative check are recorded truthfully

#### Scenario: Quick repair reveals a contract change

- **GIVEN** a repair began through quick execution
- **WHEN** investigation reveals new behavior, architecture, compatibility, data-contract, or material scope work
- **THEN** further quick implementation stops
- **AND** work continues only through requirement-first intake and its linked managed child, unless direct technical managed intent was explicit

#### Scenario: Quick task grows into a material change

- **GIVEN** work began as quick execution
- **WHEN** inspection reveals material scope or need for a full active OpenSpec contract
- **THEN** further implementation stops and the accepted scope is recorded or reused as a Business Requirement
- **AND** work continues only after pre-authoring and a linked managed technical child establish canonical OpenSpec provenance

#### Scenario: Genuine quick work has no OpenSpec change

- **GIVEN** a bounded quick task never created an active OpenSpec change
- **WHEN** it uses the supported quick lifecycle
- **THEN** absence of managed provenance alone does not force backlog creation

### Requirement: Connected-GitHub authoring verifies durable managed state before reporting success

When a ChatGPT Project authors an internal or explicitly requested direct technical managed task through connected GitHub, it SHALL read back and verify the Issue, labels, and one active supported `managed-openspec:v1` package before reporting technical authoring success.

#### Scenario: Connected authoring completes normally

- **WHEN** a ChatGPT Project records an accepted generic fixation request
- **THEN** it reads back the exact `type:requirement` Issue with business sections and target repository
- **AND** it verifies exactly the target's configured `project:*` label and one explicit or default `priority:*` label
- **AND** it reports successful fixation only after verifying that representation
- **AND** it does not publish a managed OpenSpec package or start execution

#### Scenario: Operator-managed target has no committed configuration

- **GIVEN** an operator-managed target such as Dev Platform keeps `.dev-platform.toml` untracked
- **AND** the ChatGPT Project declares Backlog repository, target repository, project label and default priority rendered by `requirement_intake.py routing-parameters`
- **WHEN** the ChatGPT Project records a Requirement for that target
- **THEN** it applies the declared project label and the explicit or default priority
- **AND** it reports success only after the same read-back verifies exactly those labels

#### Scenario: Connected Requirement routing cannot be resolved

- **WHEN** the target has no valid committed `[development_backlog]` and the declared Project parameters are missing, invalid, name another Backlog repository or another target
- **OR** declared parameters disagree with committed configuration
- **THEN** the adapter does not create a Requirement without verified project/priority metadata
- **AND** it reports the routing blocker

#### Scenario: Issue exists but package publication is incomplete

- **WHEN** an internal or explicitly requested direct technical managed task is authored through connected GitHub
- **THEN** the adapter reads back its exact Issue, configured labels, and one complete active `managed-openspec:v1` package
- **AND** it reports technical authoring success only after the existing package checks pass

#### Scenario: Partial state cannot be repaired safely

- **WHEN** connected technical authoring finds ambiguous or conflicting partial Issue/package state
- **THEN** it reports the exact blocker and does not claim technical authoring success
- **AND** it does not weaken managed-start validation or invent replacement product intent

### Requirement: Generic fixation creates a Business Requirement without technical authoring

The platform SHALL distinguish discussion from explicit fixation. Discussion alone SHALL NOT create Backlog state. A generic instruction to fix or add accepted non-trivial work to the Development Backlog SHALL create or reuse one human-facing `type:requirement` Business Requirement containing business intent and SHALL stop. It SHALL NOT create a managed OpenSpec package, technically decompose the work, or start implementation unless the same request also clearly authorizes execution.

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

### Requirement: Public managed provenance uses opaque private lineage

A managed task sourced from a private Backlog Issue SHALL keep the exact Issue reference in the existing private Issue and ignored local task state. Publicly committed active and archived OpenSpec provenance and derived validation/integration receipts SHALL retain an opaque, non-derivable lineage handle for exact private technical provenance.

#### Scenario: Private managed task is published

- **GIVEN** a managed task came from a private Backlog Issue
- **WHEN** its OpenSpec archive and verification evidence are committed
- **THEN** the public records contain its opaque lineage handle and may contain only validated readable BR identifiers as additional private-derived identity
- **AND** an authorized private Issue read can prove that handle belongs to the exact task

#### Scenario: Resume from private Issue

- **WHEN** a previously published private managed task is resumed by its exact private Issue
- **THEN** the lifecycle fetches its handle through authorized private access and accepts only the matching canonical change
- **AND** absent or ambiguous mappings fail closed

#### Scenario: Existing public archive is migrated

- **GIVEN** a completed public archive contains the old exact private Issue reference
- **WHEN** its current-tree record is sanitized
- **THEN** past check outcomes and semantic verification remain truthful
- **AND** the post-verification redaction is explicitly identified without claiming historical Git removal

#### Scenario: Shared Requirement candidate is published

- **GIVEN** verified child receipts are assembled for a private Requirement
- **WHEN** the combined candidate is committed and published
- **THEN** its public branch, commit messages, manifest, PR text and process-evidence comments preserve opaque technical handles and may expose only readable BR identifiers without private Backlog identity or contents
- **AND** the exact private manifest is checked through authorized private mapping before publication

### Requirement: Exact-target validation uses reviewed workspace storage

Managed authoring and handoff materialization SHALL validate against their exact prepared revision in an isolated helper-owned detached Git worktree under the integration checkout's existing configured platform worktree storage. This operation SHALL retain ordinary workspace admission, shared-workspace permissions and containment checks and SHALL NOT depend on manually changing TMPDIR, disable policy, or substitute another location after failure.

#### Scenario: Attached local policy with external system temporary directory

- **GIVEN** an integration checkout admitted under reviewed workspace roots and TMPDIR outside those roots
- **WHEN** managed authoring or materialize-handoff validates a package
- **THEN** its isolated detached worktree is allocated in existing platform storage inside those roots without changing TMPDIR
- **AND** validation observes the exact prepared SHA with ordinary admission and permission checks
- **AND** integration source content and branch identity remain unchanged

#### Scenario: Invalid validation storage

- **WHEN** validation storage configuration is missing or invalid, or its path escapes containment through a symlink or has foreign ownership
- **THEN** validation fails explicitly naming the unsafe storage
- **AND** no alternate directory, policy bypass or managed Issue is used

### Requirement: Validation worktree cleanup is explicit and identity bounded

Exact-target validation SHALL clean only its own verified temporary worktree and directory on success, failure and catchable interruption. A failed checkout hook that leaves a Git registration SHALL receive the same bounded cleanup. Failed cleanup SHALL be reported explicitly with retained identity evidence for safe recovery; it SHALL NOT be swallowed or replaced by unchecked recursive deletion.

#### Scenario: Validation succeeds or raises

- **WHEN** validation completes, raises an exception or receives KeyboardInterrupt
- **THEN** the exact helper-owned Git registration and temporary directory are removed
- **AND** validation errors remain visible and unrelated worktrees are untouched

#### Scenario: Checkout hook rejects the temporary checkout

- **WHEN** Git worktree add returns nonzero after creating a registration
- **THEN** cleanup verifies and removes only the helper's exact registration and temporary directory
- **AND** the original checkout failure is reported

#### Scenario: Cleanup cannot be completed

- **WHEN** cleanup fails or the helper is stopped before cleanup can run
- **THEN** available identity evidence supports explicit bounded recovery via the existing cleanup mechanism
- **AND** repeated recovery of already removed helper state is safe
- **AND** foreign, changed or ambiguous worktree state is preserved with an explicit diagnostic

#### Scenario: Unknown or unavailable cwd observation

- **WHEN** recovery receives malformed, unknown, incomplete, non-absolute or unreadable cwd records, or strict path resolution fails
- **THEN** recovery fails explicitly before removing helper state
- **AND** process and cwd descriptor headers are validated as structure

#### Scenario: Final directory removal fails or is interrupted

- **WHEN** cleanup has removed the exact Git worktree and reaches empty-directory removal
- **THEN** it first publishes the ownership receipt at the exact sibling `<helper-directory>.cleanup-owner.json` through an atomic hard link that cannot overwrite existing state
- **AND** an interruption between link and inner-receipt unlink is recoverable only for identical receipt inodes with no Git registration
- **AND** failure or interruption retains independently verifiable identity until empty-directory removal succeeds
- **AND** recovery verifies owner/process/cwd and directory inode when present, then removes only the empty directory and receipt
- **AND** an absent directory with a verified sibling receipt permits only receipt removal

### Requirement: Requirement fixation confirms Project membership

Business Requirement fixation SHALL be reported successful only after the configured Development Backlog Project (`project_owner/project_number`) holds exactly one item for the Requirement Issue, confirmed by read-back, with an initialized Status.

#### Scenario: Auto-add did not run

- **WHEN** a Requirement Issue is created and the Project holds no item for it
- **THEN** the platform adds the Issue to the configured Project, sets Status `Backlog` and reads back exactly one item before reporting success

#### Scenario: Item already present

- **WHEN** the Project already holds exactly one item for the Issue
- **THEN** no item is added and an existing Status is preserved
- **AND** repeating reconciliation is a no-op

#### Scenario: Project unavailable after Issue creation

- **WHEN** the Issue was created but the Project cannot be read or written
- **THEN** fixation fails closed naming the durable Issue and the reconciliation command
- **AND** a rerun with the same title and body continues that Issue instead of creating another

### Requirement: Business Requirement content is authored as a self-contained current contract

Before a Business Requirement body is written at fixation or materially changed at refinement, the authoring agent on every surface (repository agents and ChatGPT Project through connected GitHub) SHALL apply the single canonical Requirement authoring standard.

#### Scenario: Long discussion with several accepted details

- **GIVEN** a conversation that accepted exact texts, a scenario order and constraints
- **WHEN** the agent fixes the change
- **THEN** each material accepted detail appears in the Requirement
- **AND** a phrase such as "make it convenient" does not replace an agreed exact contract

#### Scenario: Earlier proposals were rejected

- **GIVEN** several options were discussed and one was explicitly accepted
- **WHEN** the Requirement is written
- **THEN** it states only the accepted result and any boundary that remains in force
- **AND** an unaccepted hypothesis is not presented as the user's choice

#### Scenario: A decision changes in an existing Requirement

- **WHEN** an accepted decision cancels an earlier one
- **THEN** Outcome, scenarios, Exclusions and Acceptance evidence are updated together as one current contract
- **AND** no obsolete mandatory criterion remains beside the new rule
- **AND** the children block, lifecycle-owned markers and BR revision binding are not edited by hand

#### Scenario: Fixed text versus example

- **WHEN** wording was agreed verbatim, agreed only in meaning, or offered as an optional example
- **THEN** the Requirement keeps the verbatim text verbatim, preserves every mandatory meaning of the permitted wording, and does not promote the optional example to a requirement

#### Scenario: Narrow request

- **WHEN** the accepted change is a specific prohibition or local behavior
- **THEN** the Requirement stays limited to it and creates no global policy or adjacent project

### Requirement: References are preserved reachable and unavailable material is declared

When the discussion supplied a screenshot, mockup, document, link or other reference, the Requirement SHALL preserve it through a permitted stable channel the executing agent can reach, SHALL name the properties of the reference that are mandatory, and SHALL declare any material the executor cannot access as unavailable.

#### Scenario: Reference available to the executor

- **WHEN** a mockup or link is accessible to the executing agent
- **THEN** the Requirement references it durably and states the visual or semantic properties that must hold

#### Scenario: Attachment not accessible

- **WHEN** an attachment cannot be reached by the executing agent
- **THEN** the Requirement states that it is unavailable and what is known from it
- **AND** does not point to a mutable homepage as a substitute

### Requirement: Authoring questions are limited to unresolved material product choices

Before writing, the author SHALL reconcile the conversation, supplied materials and available authoritative product context and SHALL ask the human only when proceeding would require choosing something that materially changes the product result, rights, money or data invariants, essential scope or the meaning of an earlier decision.

#### Scenario: Material product fork unresolved

- **WHEN** two incompatible outcomes remain and no accepted choice can be determined
- **THEN** the author asks a brief question with the consequence of each option rather than guessing

#### Scenario: Question already answered or immaterial

- **WHEN** the answer is already in the conversation or the gap is cosmetic or technical
- **THEN** the author does not interrupt fixation and delegates or uses the stated answer

#### Scenario: Compact obvious request

- **WHEN** the request is short and unambiguous
- **THEN** the Requirement is compact, without a questionnaire or empty subsections

### Requirement: The authoring standard is a working discipline, not a lifecycle element

Before writing and after any material edit the author SHALL check coverage, consistency, scope, autonomy, portability and truthfulness of the Requirement as a lightweight internal practice.

#### Scenario: Standard applied on a surface without checkout

- **WHEN** a ChatGPT Project fixes a Requirement through connected GitHub
- **THEN** it follows the same standard and the same Issue representation as a repository agent
- **AND** no extra stage, gate or user action is added

#### Scenario: Existing process is unchanged

- **WHEN** a Requirement authored under the standard is created, read back, started and executed
- **THEN** routing, labels, Project membership, children block, revision binding and ADD/OpenSpec behave as before

## ADDED Requirements

### Requirement: Incomplete managed-start recovery acts only on its own task transaction

Recovery of incomplete managed-start creation state SHALL act only on the worktree, branch and agent-board entry named by that task's own transaction, and SHALL refuse when the candidate has commits not reachable from the main branch, dirty paths not owned by that task, task-local state naming a different source issue or change, an ambiguous board match, or cannot be proven to be an exact registered Git worktree.

#### Scenario: Recovery targets

- **WHEN** incomplete managed-start creation state is recovered
- **THEN** only the worktree, branch and agent-board entry named by that task's own transaction are acted on

#### Scenario: Unsafe candidate

- **WHEN** the candidate has commits not reachable from main, dirty paths not owned by the task, task-local state naming a different source issue or change, an ambiguous board match, or is not provably an exact registered Git worktree
- **THEN** recovery refuses

### Requirement: Incomplete managed-start recovery performs no global pruning

Recovery of incomplete managed-start creation state SHALL NOT perform global worktree or board pruning.

#### Scenario: Recovery runs

- **WHEN** incomplete managed-start creation state is recovered
- **THEN** no global worktree or board pruning is performed

### Requirement: Fresh non-trivial execution intent authorizes intake without a separate fixation request

Execution intent for a fresh non-trivial change SHALL authorize creating or reusing a Business Requirement, running requirement-first pre-authoring, and linking, starting and implementing each resulting internal managed OpenSpec child without a separate fixation request.

#### Scenario: User asks to execute

- **WHEN** a user asks to execute a fresh non-trivial change
- **THEN** the Business Requirement, requirement-first pre-authoring and each resulting managed child proceed without a separate fixation request

### Requirement: A quick repair identifies the accepted contract and keeps regression evidence

A quick repair that restores unambiguously accepted behavior SHALL identify the accepted contract and retain proportionate regression evidence.

#### Scenario: Quick repair

- **WHEN** quick execution repairs unambiguously accepted behavior
- **THEN** the repair identifies the accepted contract
- **AND** proportionate regression evidence is retained

### Requirement: A quick repair regression check fails before and passes after the repair

When a reasonable test seam exists for a quick repair, its regression check SHALL fail before the repair and pass after it, and the original failure path SHALL be rerun.

#### Scenario: Test seam exists

- **WHEN** a reasonable test seam exists for the quick repair
- **THEN** its regression check fails before the repair and passes after it
- **AND** the original failure path is rerun

### Requirement: A quick repair without a test seam records its limitation

When no reasonable seam exists for a quick repair, the limitation and the actual alternative check SHALL be recorded without fabricated evidence.

#### Scenario: No test seam

- **WHEN** no reasonable seam exists for the quick repair
- **THEN** the limitation and the actual alternative check are recorded
- **AND** no evidence is fabricated

### Requirement: Quick execution keeps applicable gates

Applicable safety, check, verification, and publication gates SHALL still apply to quick execution.

#### Scenario: Quick work published

- **WHEN** quick execution is used
- **THEN** the applicable safety, check, verification, and publication gates still apply

### Requirement: Material quick work stops and enters requirement-first intake

If quick work changes behavior, architecture, compatibility, a data contract, or material scope, or needs a full active OpenSpec change, the platform SHALL stop further quick implementation and enter requirement-first intake, except when the user explicitly requests the direct technical managed path.

#### Scenario: Quick work becomes material

- **WHEN** quick work changes behavior, architecture, compatibility, a data contract, or material scope, or needs a full active OpenSpec change
- **THEN** further quick implementation stops and requirement-first intake is entered

#### Scenario: Direct technical path requested

- **WHEN** the user explicitly requests the direct technical managed path
- **THEN** that path is used instead of requirement-first intake

### Requirement: Quick work escalation uses the existing lifecycles

Quick execution and its escalation to requirement-first intake SHALL use the existing quick and managed lifecycles and SHALL NOT change release-bundling policy.

#### Scenario: Quick work escalated

- **WHEN** quick work runs or escalates to requirement-first intake
- **THEN** the existing quick and managed lifecycles are used
- **AND** release-bundling policy is unchanged

### Requirement: Connected-GitHub generic fixation verifies the durable Business Requirement

Instead of the Issue, labels and `managed-openspec:v1` package read-back required for connected-GitHub managed technical authoring, generic fixation through connected GitHub SHALL verify the durable Business Requirement representation, including exactly one configured `project:*` label and exactly one `priority:*` label, without requiring or publishing any managed OpenSpec package.

#### Scenario: Generic fixation from ChatGPT

- **WHEN** a ChatGPT Project performs generic fixation through connected GitHub
- **THEN** it verifies the durable Business Requirement with exactly one configured `project:*` label and exactly one `priority:*` label
- **AND** no managed OpenSpec package is required or published

### Requirement: Connected Requirement routing uses committed development_backlog configuration

Connected Requirement routing SHALL come from the existing project/operator `[development_backlog]` configuration. Connected Requirement routing SHALL use the target repository's committed configuration when present.

#### Scenario: Target tracks configuration

- **WHEN** the target repository has committed `[development_backlog]` configuration
- **THEN** connected Requirement routing uses that committed configuration

### Requirement: Connected Requirement routing for operator-managed repositories uses declared Project parameters

When the target intentionally does not track the `[development_backlog]` configuration (an operator-managed repository), connected Requirement routing SHALL use the operator-declared Project parameters rendered from that same configuration.

#### Scenario: Operator-managed repository

- **WHEN** the target intentionally does not track the `[development_backlog]` configuration
- **THEN** connected Requirement routing uses the operator-declared Project parameters rendered from that configuration

### Requirement: Declared connected routing parameters that disagree with committed configuration conflict

Declared Project parameters for connected Requirement routing that disagree with committed `[development_backlog]` configuration SHALL be a conflict.

#### Scenario: Declared parameters disagree

- **WHEN** declared Project parameters disagree with the committed configuration
- **THEN** connected Requirement routing reports a conflict

### Requirement: Connected Requirement routing adds no second source or hardcoded values

The platform SHALL NOT introduce a second routing source for connected Requirement routing or hardcode a concrete label, priority or operator configuration in public source.

#### Scenario: Public source inspected

- **WHEN** connected Requirement routing is implemented
- **THEN** no second routing source exists
- **AND** public source hardcodes no concrete label, priority or operator configuration

### Requirement: An explicit technical managed task request stays eligible for direct authoring

An explicit request for a technical managed task SHALL remain eligible for the direct technical managed authoring path.

#### Scenario: Technical managed task requested

- **WHEN** the user explicitly requests a technical managed task
- **THEN** the request remains eligible for the direct technical managed authoring path

### Requirement: No public managed object contains private Backlog data

Readable BR-N and BR-N/Tn identifiers derived only from the parent Requirement number and stable child ordinal MAY be published; the parent Requirement number itself is not secret. No public object SHALL contain the private Backlog name or URL, exact private Issue reference, Requirement text or other private data.

#### Scenario: Public objects published

- **WHEN** managed provenance from a private Backlog Issue is published
- **THEN** no public object contains the private Backlog name or URL, exact private Issue reference, Requirement text or other private data
- **AND** readable BR-N and BR-N/Tn identifiers may appear

### Requirement: Opaque lineage handle mapping lives in the private Backlog Issue

The opaque lineage handle mapping SHALL live in the same private Backlog Issue that keeps the exact Issue reference; no second storage service is added.

#### Scenario: Handle mapping stored

- **WHEN** an opaque lineage handle is assigned
- **THEN** its mapping is stored in the same private Backlog Issue
- **AND** no second storage service is used

### Requirement: Missing or conflicting lineage handle mapping blocks archive and publication

Missing or conflicting opaque lineage handle mapping SHALL block archive or publication.

#### Scenario: Mapping missing or conflicting

- **WHEN** the opaque lineage handle mapping is missing or conflicting
- **THEN** archive or publication is blocked

### Requirement: Exact-target validation storage failures fail before managed Issue creation

For exact-target validation, missing or invalid required storage configuration, unsafe containment or ownership, and admission failures SHALL fail explicitly before managed Issue creation.

#### Scenario: Storage not usable

- **WHEN** exact-target validation finds missing or invalid storage configuration, unsafe containment or ownership, or an admission failure
- **THEN** it fails explicitly before the managed Issue is created

### Requirement: Exact-target validation recovery after interruption is idempotent and bounded

Recovery of exact-target validation after interruption SHALL be idempotent and use existing lifecycle cleanup mechanisms without taking over foreign or ambiguous worktrees.

#### Scenario: Recovery repeated

- **WHEN** recovery after an interrupted exact-target validation runs more than once
- **THEN** it is idempotent and uses existing lifecycle cleanup mechanisms
- **AND** no foreign or ambiguous worktree is taken over

### Requirement: A missing Requirement Project item is added idempotently

GitHub built-in auto-add MAY supply the Development Backlog Project item for the Requirement Issue, but its absence SHALL be repaired by an idempotent add through the existing Project authorization and SHALL NOT be assumed.

#### Scenario: Auto-add did not supply the item

- **WHEN** the configured Development Backlog Project has no item for the Requirement Issue
- **THEN** the item is added idempotently through the existing Project authorization

### Requirement: Project labels are not proof of Project membership

`project:*` labels SHALL NOT be treated as proof of Development Backlog Project membership.

#### Scenario: Label present

- **WHEN** the Requirement Issue carries a `project:*` label
- **THEN** Project membership is still confirmed by read-back of the Project item

### Requirement: Requirement Project item Status is initialized without overwrite

An unset Status of the Development Backlog Project item for the Requirement Issue SHALL be initialized to `Backlog`; an existing Status SHALL NOT be overwritten.

#### Scenario: Status unset

- **WHEN** the Project item has no Status
- **THEN** Status is initialized to `Backlog`

#### Scenario: Status already set

- **WHEN** the Project item already has a Status
- **THEN** that Status is not overwritten

### Requirement: Requirement fixation fails explicitly on Project membership errors

During Business Requirement fixation, more than one Development Backlog Project item for the Requirement Issue, an unavailable Project, or a failed read-back SHALL fail explicitly naming the Requirement.

#### Scenario: Membership cannot be confirmed

- **WHEN** the Project holds more than one item for the Requirement, is unavailable, or the read-back fails
- **THEN** fixation fails explicitly naming the Requirement

### Requirement: Business Requirement authors use whole context and separate material kinds

The Business Requirement author SHALL use the whole relevant available context, SHALL separate accepted current requirements, explicitly accepted superseding refinements, examples and references, rejected or hypothetical material, and genuinely open material, and SHALL write only the current agreed result in affirmative form.

#### Scenario: Mixed discussion material

- **WHEN** the author writes a Business Requirement from discussion containing accepted, superseding, example, rejected, hypothetical and open material
- **THEN** the author separates these kinds using the whole relevant available context
- **AND** only the current agreed result is written in affirmative form

### Requirement: A later accepted Business Requirement decision replaces an earlier one

In Business Requirement authoring, a later explicitly accepted decision SHALL replace an earlier one; a last-mentioned option, an agent suggestion, a quotation or a hypothesis SHALL NOT be treated as accepted.

#### Scenario: Decision superseded

- **WHEN** a later decision is explicitly accepted
- **THEN** it replaces the earlier one in the Requirement

#### Scenario: Unaccepted material

- **WHEN** the discussion ends with a last-mentioned option, an agent suggestion, a quotation or a hypothesis
- **THEN** it is not treated as accepted

### Requirement: Business Requirements carry no negotiation history

Negotiation history SHALL NOT be copied into a Business Requirement; a still-active boundary SHALL be stated as the boundary and its material condition.

#### Scenario: Negotiated boundary

- **WHEN** a boundary was negotiated and is still active
- **THEN** the Requirement states the boundary and its material condition
- **AND** the negotiation history is not copied

### Requirement: A Business Requirement is understandable without the conversation

The Business Requirement SHALL be understandable by an agent without the conversation, using only the Requirement and the materials it directly references.

#### Scenario: Agent reads the Requirement

- **WHEN** an agent without the conversation reads the Requirement and the materials it directly references
- **THEN** the agent can understand the Requirement

### Requirement: Business Requirement authoring carries over defined detail without loss

In Business Requirement authoring, material, already-defined detail SHALL be carried over without loss: actors, rights and constraining contexts; scenarios, order, transitions, important exceptions and negative paths; agreed names, fields and input/answer rules; exact user-facing text and permitted wording; invariants for safety, truthfulness and compatibility; visual and interaction requirements; accepted delivery and acceptance conditions and explicit exclusions.

#### Scenario: Defined detail exists

- **WHEN** the discussion already defined material detail such as actors, scenarios, names, exact user-facing text, invariants, visual requirements or acceptance conditions
- **THEN** the Requirement carries that detail over without loss

### Requirement: Business Requirement binding levels are evident

In a Business Requirement, binding SHALL be evident at three levels: fixed (not changed without re-agreement), meaning fixed with variable execution, and delegated within the accepted corridor; delegation SHALL NOT permit changing product meaning, safety boundaries, data, rights or accepted scenarios, and SHALL NOT require agreement on immaterial choices.

#### Scenario: Binding levels shown

- **WHEN** a Requirement states its content
- **THEN** each part is evidently fixed, meaning fixed with variable execution, or delegated within the accepted corridor

#### Scenario: Delegated part

- **WHEN** a part is delegated
- **THEN** the delegation does not permit changing product meaning, safety boundaries, data, rights or accepted scenarios
- **AND** it does not require agreement on immaterial choices

### Requirement: Business Requirement acceptance evidence describes observable results

Business Requirement acceptance evidence SHALL describe observable results and, where material, successful, failing and forbidden behavior.

#### Scenario: Acceptance evidence written

- **WHEN** the Requirement states acceptance evidence
- **THEN** it describes observable results and, where material, successful, failing and forbidden behavior

### Requirement: Business Requirement authoring does not widen a narrow request

In Business Requirement authoring, a narrow request SHALL NOT be widened into a global policy, a neighboring change or an unrequested feature.

#### Scenario: Narrow request

- **WHEN** the request is narrow
- **THEN** the Requirement does not widen it into a global policy, a neighboring change or an unrequested feature

### Requirement: Business Requirement length follows content

Business Requirement length SHALL follow the content, not a template.

#### Scenario: Requirement length

- **WHEN** a Requirement is written
- **THEN** its length follows the content, not a template

### Requirement: Requirement references are not replaced by site roots or copied privately

The Requirement SHALL NOT replace an unavailable attachment with a link to a changing site root, and SHALL NOT copy private conversations, secrets, unreachable personal files or whole external documents into a public repository.

#### Scenario: Attachment unavailable

- **WHEN** a supplied attachment is unavailable
- **THEN** the Requirement does not replace it with a link to a changing site root

#### Scenario: Private material

- **WHEN** the discussion includes private conversations, secrets, unreachable personal files or whole external documents
- **THEN** the Requirement does not copy them into a public repository

### Requirement: Requirement authoring questions are brief and grouped

Requirement authoring questions SHALL be brief, grouped (normally one to three per pass), explain the choice and consequence where useful, and SHALL NOT repeat an answered question, ask a technical ADD/OpenSpec question, demand empty sections or run a mandatory interview.

#### Scenario: Author asks

- **WHEN** the author asks the human authoring questions
- **THEN** they are brief, grouped (normally one to three per pass) and explain the choice and consequence where useful
- **AND** no answered question is repeated, no technical ADD/OpenSpec question is asked, no empty section is demanded and no mandatory interview is run

### Requirement: Minor missing Requirement detail is delegated to the executor

Minor missing detail SHALL be delegated to the executor and the Requirement fixed without delay.

#### Scenario: Minor detail missing

- **WHEN** only minor detail is missing
- **THEN** it is delegated to the executor
- **AND** the Requirement is fixed without delay

### Requirement: A critical unresolved Requirement choice is not written as agreed

A critical unresolved choice SHALL NOT be written as agreed; the author asks before fixation or keeps the idea as an incubated, unaccepted item under the existing Incubator contract.

#### Scenario: Critical choice unresolved

- **WHEN** a critical choice is unresolved
- **THEN** it is not written as agreed
- **AND** the author asks before fixation or keeps the idea as an incubated, unaccepted item under the existing Incubator contract

### Requirement: The pre-fixation authoring question check does not replace ADD/OpenSpec resolution

The pre-fixation authoring question check SHALL NOT replace later evidence-first ADD/OpenSpec resolution.

#### Scenario: Later technical resolution

- **WHEN** a Requirement passed the pre-fixation check
- **THEN** later evidence-first ADD/OpenSpec resolution still applies

### Requirement: The Requirement authoring check adds no lifecycle machinery

The author's Requirement coverage, consistency, scope, autonomy, portability and truthfulness check SHALL NOT introduce a blocking or LLM semantic validator, scorecard, approval stage, lifecycle status, separate backlog, list of unresolved questions, per-project configuration or new storage, and SHALL NOT change the Requirement format, routing, labels, children markers, BR revision binding, pre-authoring or quick-task behavior.

#### Scenario: Authoring check applied

- **WHEN** the author performs the Requirement check
- **THEN** no blocking or LLM semantic validator, scorecard, approval stage, lifecycle status, separate backlog, unresolved-question list, per-project configuration or new storage is introduced
- **AND** the Requirement format, routing, labels, children markers, BR revision binding, pre-authoring and quick-task behavior are unchanged

### Requirement: Requirement fixation transport is unchanged and does not start implementation

Transport and confirmation of Requirement fixation SHALL remain as specified, and creating the Requirement SHALL NOT start implementation.

#### Scenario: Requirement fixed

- **WHEN** a Requirement is created under the authoring standard
- **THEN** fixation transport and confirmation remain as specified
- **AND** implementation is not started
