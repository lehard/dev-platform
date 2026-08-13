# managed-task-intake Specification

## Purpose
TBD - created by archiving change add-managed-backlog-intake. Update Purpose after archive.
## Requirements
### Requirement: Managed tasks use a versioned central intake package

A managed task SHALL be represented by a human-readable issue in the configured Development Backlog plus exactly one supported managed OpenSpec package. The package SHALL identify its format version, source issue, target repository, OpenSpec change name, preparation commit for the target repository, and the complete set of planning artifacts required for implementation.

#### Scenario: ChatGPT prepares a managed task

- **WHEN** a non-trivial change is explicitly fixed into the Development Backlog
- **THEN** the issue contains the human task description and OpenSpec change name
- **AND** a `managed-openspec:v1` package contains the source issue, target repository, preparation commit and OpenSpec artifacts
- **AND** no implementation is started merely because the package exists

#### Scenario: Multiple supported packages are present

- **WHEN** intake finds zero packages, more than one current package, an unsupported version, or an incomplete manifest
- **THEN** import fails closed with an actionable error
- **AND** no OpenSpec files are partially materialized

### Requirement: Managed-task import is deterministic and target-safe

The platform SHALL provide a dependency-light import entrypoint that reads a managed task using existing authenticated GitHub access, verifies that the package target matches the current repository, constrains every supplied artifact to the new OpenSpec change root, and never executes package text as shell or code.

#### Scenario: Correct task is imported from the target repository

- **GIVEN** the current checkout resolves to the package target repository
- **AND** the package is structurally valid
- **WHEN** the managed-task import entrypoint is invoked
- **THEN** it creates the change scaffold using the installed OpenSpec CLI and repository schema
- **AND** writes only the declared OpenSpec artifacts under that change
- **AND** records provenance sufficient to identify the source issue and imported package revision
- **AND** does not start apply or edit application/platform implementation files

#### Scenario: Task targets a different repository

- **WHEN** the package target repository does not equal the normalized current `origin` repository identity
- **THEN** import aborts before creating or changing the OpenSpec change

#### Scenario: Package declares an unsafe artifact path

- **WHEN** an artifact path is absolute, traverses outside the change root, targets `.git`, or otherwise escapes the allowed planning area
- **THEN** import rejects the package before writing any artifact

### Requirement: Import uses the repository's current OpenSpec contract

Managed-task import SHALL use the installed OpenSpec CLI to create/inspect the change under the repository's current configured schema instead of assuming a fixed directory layout from the transport package alone. The transport package SHALL supply planning content, not replace OpenSpec schema discovery.

#### Scenario: Repository schema has evolved since package preparation

- **WHEN** the current OpenSpec CLI/schema requires a different scaffold or artifact contract than the package assumed
- **THEN** import/preflight reports the incompatibility
- **AND** does not silently invent or discard product semantics merely to force the package through validation

#### Scenario: Structural validation succeeds

- **WHEN** all package artifacts are materialized into a compatible scaffold
- **THEN** the importer runs the repository-supported structural OpenSpec preflight
- **AND** reports that semantic preflight is still required before implementation

### Requirement: Package freshness is explicit and semantic preflight is mandatory when needed

A managed package SHALL record the target repository commit used during preparation. Import SHALL compare that evidence with current synchronized target state. A changed target commit SHALL not automatically invalidate unrelated planning, but it SHALL be surfaced so an agent cannot blindly apply an old contract.

#### Scenario: Target main is unchanged

- **WHEN** the synchronized target commit equals `prepared_against`
- **THEN** import reports the package as freshness-aligned
- **AND** the normal semantic OpenSpec review still applies before implementation

#### Scenario: Target main advanced after preparation

- **WHEN** synchronized target main differs from `prepared_against`
- **THEN** import reports the package as stale relative to repository state
- **AND** the agent reviews relevant current specs and active changes before implementation
- **AND** a material product-contract conflict requires user resolution rather than silent rewriting

### Requirement: Re-import is idempotent and never silently overwrites divergent work

The importer SHALL compute and persist provenance for the imported package so retrying the same task is safe. It SHALL distinguish an unchanged imported package from a package that changed after local materialization or from an unrelated same-name OpenSpec change.

#### Scenario: Same unchanged package is imported again

- **GIVEN** the existing local change was imported from the same source issue and package revision
- **WHEN** import is repeated
- **THEN** it verifies/reuses the existing change without duplicating artifacts or destroying edits

#### Scenario: Backlog package changed after materialization

- **GIVEN** the local change already records an earlier package revision
- **WHEN** the source issue now contains a different package revision
- **THEN** the importer stops and requires explicit reconciliation
- **AND** does not overwrite the repository-local OpenSpec automatically

#### Scenario: Same change name belongs to another source

- **WHEN** a local active change with the requested name exists but its provenance does not match the source issue
- **THEN** import fails closed and reports the naming conflict

### Requirement: Intake authentication adds no new secret boundary

Managed-task intake SHALL reuse existing validated GitHub CLI/API credentials and the installed OpenSpec CLI. It SHALL NOT require a new daemon, cloud service, API key, or committed credential.

#### Scenario: GitHub issue cannot be read

- **WHEN** existing GitHub authentication is unavailable or insufficient for the private backlog repository
- **THEN** import fails with an authentication/setup message
- **AND** does not partially create the OpenSpec change

### Requirement: Intake does not own dispatch or Project workflow state

The v1 importer SHALL prepare planning state only. It SHALL NOT poll GitHub Project `Ready`, launch Codex/Claude, change Project status, merge code, or replace the existing dev-platform execution/publication lifecycle.

#### Scenario: Managed task is imported successfully

- **WHEN** import and structural preflight complete
- **THEN** the task is ready for the existing agent/OpenSpec execution flow
- **AND** no background execution or Project-status mutation is triggered by the importer

### Requirement: Explicit fixation intent creates a managed task without starting implementation

The platform SHALL define an explicit managed-task authoring path for non-trivial work discussed with a repository agent. Discussion or exploration alone SHALL NOT create backlog state. When the user clearly asks to fix/record/add the accepted change to the Development Backlog, the agent SHALL create the managed task and its OpenSpec package, then stop before implementation.

#### Scenario: User is still discussing alternatives

- **WHEN** the user and agent are exploring requirements, architecture, tradeoffs or implementation options without an explicit fixation request
- **THEN** no Development Backlog issue or managed OpenSpec package is created solely because the discussion is detailed
- **AND** the agent may continue analysis without starting implementation unless separately requested

#### Scenario: User explicitly asks to fix the accepted change

- **GIVEN** the discussion has converged on a non-trivial accepted result
- **WHEN** the user says “зафиксируй”, “добавь в бэклог”, “создай задачу”, “отправь в бэклог” or an equivalent unambiguous authoring instruction
- **THEN** the agent consolidates only the currently accepted decision
- **AND** prepares a human-readable managed task plus complete OpenSpec package
- **AND** invokes the standard authoring entrypoint
- **AND** does not begin apply, coding, task start, dispatch or publication after successful creation

### Requirement: Managed-task authoring uses repository configuration and current target identity

A participating repository SHALL expose configuration sufficient to author a task into the shared Development Backlog without hard-coded per-agent instructions. The configuration SHALL include the backlog repository, project label and default priority. The target repository SHALL be derived from the normalized current GitHub `origin` identity.

#### Scenario: Agent authors from a configured managed repository

- **WHEN** the authoring helper runs in a participating repository
- **THEN** it resolves the Development Backlog repository and `project:*` label from repository configuration
- **AND** resolves the target repository from the current checkout origin
- **AND** uses `priority:P2` when the user did not explicitly select another supported priority

#### Scenario: Required authoring configuration is missing or invalid

- **WHEN** backlog repository, project label, target GitHub origin or supported priority cannot be resolved unambiguously
- **THEN** authoring fails closed with an actionable error
- **AND** no partial Issue/package is published

### Requirement: Authoring preserves the existing managed-openspec:v1 transport contract

The authoring helper SHALL publish exactly one valid `managed-openspec:v1` package that can be consumed by the existing managed-task importer. It SHALL not invent a second transport representation for Codex/Claude-authored tasks.

#### Scenario: Managed task is created successfully

- **GIVEN** the agent has prepared the required OpenSpec planning artifacts
- **WHEN** authoring publishes the task
- **THEN** the Issue contains the configured target repository and OpenSpec change name
- **AND** exactly one `managed-openspec:v1` package identifies the new source issue, target repository, change name, preparation commit and complete declared artifacts
- **AND** the package format is directly consumable by the standard importer

#### Scenario: Prepared artifacts cannot satisfy the current OpenSpec contract

- **WHEN** required planning artifacts are missing, empty, unsafe, ambiguous or incompatible with the repository's current OpenSpec schema
- **THEN** authoring stops before publishing an incomplete managed task
- **AND** reports the planning incompatibility for the agent to repair or escalate

### Requirement: Model-owned planning and helper-owned publication remain separate

The agent/model SHALL own semantic planning content, while the authoring helper SHALL own deterministic GitHub and package mechanics. The helper SHALL not invent product requirements or implementation design, and the model SHALL not be required to hand-assemble GitHub API calls or transport delimiters for normal authoring.

#### Scenario: Agent prepares a change after discussion

- **WHEN** a managed task is ready to author
- **THEN** the agent supplies the accepted human task description and OpenSpec artifacts to the helper through the supported local interface
- **AND** the helper validates configuration/package structure, creates the Issue, applies configured labels and attaches the package
- **AND** the helper does not rewrite semantic requirements merely to make the package publishable

### Requirement: Authoring checks for an obvious open duplicate before creation

Managed-task authoring SHALL perform a bounded duplicate check against open issues in the configured Development Backlog for the same project/target before creating a new issue. It SHALL avoid silently creating an obvious duplicate while not pretending that fuzzy similarity can resolve ambiguous product scope automatically.

#### Scenario: Clear duplicate already exists

- **WHEN** the bounded duplicate check finds an open managed task that unambiguously represents the same change
- **THEN** authoring does not create a second issue
- **AND** returns the existing issue for the agent to update or report according to the user’s accepted decision

#### Scenario: Potential overlap is ambiguous

- **WHEN** an existing open task is related but it is unclear whether the new decision belongs in that task or is a separate change
- **THEN** authoring stops before creating a duplicate
- **AND** the agent asks the user to resolve the scope boundary

#### Scenario: No obvious duplicate exists

- **WHEN** the bounded check finds no materially same open task
- **THEN** authoring may create the new managed task normally

### Requirement: Authoring does not materialize or execute the target change

Managed-task authoring SHALL leave the target repository free of a persistent active OpenSpec change for the newly scheduled work and SHALL not invoke the implementation lifecycle. Temporary local validation artifacts MAY be used only if they are safely contained and removed before authoring succeeds.

#### Scenario: Task is successfully added to Backlog

- **WHEN** the central Issue and package are created
- **THEN** no persistent `openspec/changes/<change>` is left in the target repository solely from authoring
- **AND** no `start_task`, apply, implementation, finish, dispatcher or Project-status mutation is triggered
- **AND** later execution still begins by importing the managed task through the standard intake path

### Requirement: Repository agents share one managed-task authoring contract

Codex and Claude Code SHALL receive the same repository-wide managed-task semantics from the canonical agent contract. Tool-specific instruction files MAY reference that contract but SHALL NOT maintain divergent copies of the managed-task rules.

#### Scenario: Claude Code opens a generated repository

- **WHEN** Claude Code reads the repository instructions
- **THEN** `CLAUDE.md` directs it to the canonical `AGENTS.md` contract
- **AND** the managed-task authoring behavior is not separately duplicated in Claude-specific text

#### Scenario: Codex opens the same repository

- **WHEN** Codex reads the repository agent instructions
- **THEN** it receives the same discussion/fixation/quick/import semantics from `AGENTS.md`
- **AND** the resulting managed task uses the same helper/config/package contract as Claude

### Requirement: Managed-task provenance remains resolvable after materialization

After a managed package is materialized, the repository SHALL retain deterministic provenance sufficient to resolve the source Development Backlog Issue and canonical repository-local OpenSpec change during later resume and delivery. The original package content SHALL NOT become a second canonical implementation plan.

#### Scenario: Managed task resumes with an active canonical change

- **GIVEN** a managed task was materialized from source Issue A
- **AND** the repository-local active change records matching provenance to Issue A
- **WHEN** execution resumes from the existing branch/worktree
- **THEN** the lifecycle reuses that canonical change
- **AND** does not re-import or overwrite it from the original backlog package

#### Scenario: Managed task resumes after canonical change was archived

- **GIVEN** the matching repository-local change was semantically verified and archived
- **WHEN** only publication/reconciliation work remains
- **THEN** provenance to Issue A remains resolvable from the archived lifecycle evidence
- **AND** resume does not create a second active change

#### Scenario: Canonical change is missing or belongs to another source

- **WHEN** a managed branch/worktree/PR claims source Issue A but no matching active/archived canonical change exists, or the same-name change records different provenance
- **THEN** managed resume fails closed with an actionable recovery state
- **AND** does not continue implementation/publication based only on branch, PR title or change name

### Requirement: Canonical OpenSpec may evolve without losing source provenance

The platform SHALL distinguish legitimate repository-local OpenSpec evolution from provenance loss. A canonical managed change MAY diverge from the original transport package under the existing no-silent-divergence rules, while retaining its source Issue identity.

#### Scenario: Implementation updates design or tasks after materialization

- **GIVEN** the repository-local change still identifies the same source managed Issue
- **WHEN** implementation validly updates proposal/design/spec/tasks according to the repository lifecycle
- **THEN** later provenance validation accepts the evolved canonical change
- **AND** does not require byte equality with the original managed package

### Requirement: Fresh managed start is isolated from stale integration task state

A fresh managed task SHALL be distinguishable from resume of an existing managed task before first materialization. Task-specific state inherited from shared integration state SHALL NOT by itself establish the identity or resume status of the new task.

#### Scenario: Integration baseline contains stale task state

- **GIVEN** integration `main` exposes task state for managed task B
- **AND** managed task A has a valid central package but no repository-local canonical change yet
- **WHEN** task A starts through the managed intake path
- **THEN** the lifecycle treats A as a fresh task rather than a resume of A or B
- **AND** does not require canonical OpenSpec provenance for A before first materialization
- **AND** does not adopt source Issue B as A's identity

#### Scenario: Existing task is genuinely resumed

- **GIVEN** task A has an existing task worktree/branch with task-local identity and matching active or archived canonical provenance
- **WHEN** task A is resumed
- **THEN** the existing resume provenance guards remain authoritative
- **AND** the transport package is not re-applied over the canonical repository-local change

#### Scenario: Integration state belongs to another task during fresh start

- **WHEN** fresh task A observes integration-visible managed state for task B
- **THEN** that state is treated as contamination or non-authoritative integration evidence
- **AND** task A either materializes safely using its exact package identity or enters an explicit bounded recovery path
- **AND** the lifecycle does not guess or silently rewrite either task identity

### Requirement: Managed task-specific state does not become shared authoritative identity

Task-specific lifecycle state SHALL be scoped or cleaned so that completion of one managed task cannot make the next task checkout inherit that task as authoritative identity. The implementation MAY choose storage locality, cleanup, or explicit classification semantics, but SHALL preserve deterministic resume and recovery behavior.

#### Scenario: Managed task completes and another task starts

- **GIVEN** task B has reached terminal delivery
- **WHEN** later task A starts from the current integration baseline
- **THEN** task B's task-specific state cannot cause task A to enter resume-only provenance validation
- **AND** task A resolves identity from its own package/task evidence

#### Scenario: Existing contaminated baseline needs recovery

- **GIVEN** integration state already contains stale task-specific identity from a terminal task
- **WHEN** an operator starts the intended next managed task
- **THEN** the platform provides or documents a bounded recovery path that verifies the stale identity and preserves the new task's exact package identity
- **AND** recovery is idempotent
- **AND** recovery does not become a generic provenance-guard bypass

### Requirement: Terminal managed identity remains bound to the executing task

After a managed task is materialized, the platform SHALL preserve enough task-local identity to attribute all later managed side effects to that exact task. Repository or integration state belonging to another managed task SHALL NOT replace the executing task's source Issue or canonical change identity.

#### Scenario: Integration checkout contains stale task state

- **GIVEN** task A has matching task-local managed provenance
- **AND** the integration checkout exposes a state marker or package for task B
- **WHEN** task A reaches publication or terminal reconciliation
- **THEN** task A remains attributed to source Issue A
- **AND** Issue B is not selected or mutated as a substitute

#### Scenario: Multiple archived managed packages exist

- **GIVEN** the repository contains archived packages for several completed managed tasks
- **WHEN** one exact task resumes only terminal delivery/reconciliation
- **THEN** the lifecycle resolves the source identity belonging to that task's provenance/delivery
- **AND** does not select another archive merely because it is visible from integration main

#### Scenario: Task and integration identity disagree

- **WHEN** authoritative task-local identity disagrees with integration-visible managed state
- **THEN** the platform reports an explicit provenance mismatch
- **AND** blocks managed side-effect mutation until the mismatch is resolved
- **AND** does not guess which Development Backlog Issue should be updated

#### Scenario: Quick task has no managed source

- **WHEN** an ordinary quick task reaches terminal delivery without managed provenance
- **THEN** no Development Backlog managed identity is invented
- **AND** managed Project-status reconciliation remains a no-op for that task

### Requirement: Authoring validates against the exact prepared target revision

Managed-task authoring SHALL validate a package against the same target repository revision that it records as `prepared_against`. A freshly fetched remote revision SHALL NOT be recorded as preparation evidence while semantic/structural validation is actually performed against a different stale local spec state.

#### Scenario: Local authoring checkout is stale

- **GIVEN** target `origin/main` has advanced beyond the local authoring checkout
- **WHEN** authoring prepares a package against the fetched remote revision
- **THEN** validation observes the exact fetched target state or authoring fails closed before publication
- **AND** the package is not represented as validated against a state it did not inspect

#### Scenario: Exact target state cannot be established

- **WHEN** authoring cannot safely establish the repository/spec state for the recorded `prepared_against` revision
- **THEN** no Issue/package publication occurs
- **AND** the diagnostic explains the synchronization or validation blocker

### Requirement: Managed packages carry bounded source-Issue revision evidence

Newly authored managed packages SHALL retain bounded machine-comparable evidence of the source Development Backlog Issue revision used during authoring. The evidence SHALL be sufficient to detect a later meaningful Issue edit without storing a second full canonical implementation plan.

#### Scenario: Source Issue changes before materialization

- **GIVEN** a package was authored from source Issue revision A
- **AND** the source Issue is materially edited to revision B before implementation starts
- **WHEN** managed start/import evaluates the task
- **THEN** the drift is reported before implementation
- **AND** the executor must explicitly reconcile/supersede the package or acknowledge that revision A remains the intended scope
- **AND** the old package is not silently treated as current human intent

#### Scenario: Source Issue changes after materialization

- **GIVEN** a package has already been materialized into canonical repository-local OpenSpec
- **WHEN** the human-facing Issue is edited later
- **THEN** lifecycle status can expose bounded drift evidence
- **AND** repository-local OpenSpec is not automatically overwritten or broadened

### Requirement: Published managed package revisions can be superseded safely before execution

The platform SHALL provide one supported idempotent operation to replace a published managed package revision when the transport is invalid or accepted pre-execution planning has been revised. The replacement SHALL be fully validated before becoming active, SHALL preserve bounded predecessor revision evidence, and SHALL leave exactly one active package revision for deterministic import.

#### Scenario: Invalid published package is repaired

- **GIVEN** the current package cannot pass supported intake validation
- **WHEN** an operator supplies a corrected authoring bundle through the supported repair/supersede path
- **THEN** the replacement is validated against current exact target state before activation
- **AND** the old revision is marked superseded by bounded revision evidence
- **AND** the importer resolves exactly one active revision without hand-editing GitHub content

#### Scenario: Supersede is retried with identical content

- **GIVEN** the requested replacement revision is already active
- **WHEN** the same supersede operation is retried
- **THEN** it converges as a no-op
- **AND** no duplicate active package is created

#### Scenario: Package revision history is ambiguous

- **WHEN** intake observes more than one active package revision or malformed supersession metadata
- **THEN** import fails closed before materialization
- **AND** reports the revision ambiguity rather than guessing

### Requirement: Managed-start mutation is guarded by a persisted per-change transaction

Before any worktree or agent-board mutation for a managed start in a multi-agent-profile checkout, the platform SHALL persist a machine-local, per-change start transaction identifying the exact package (source issue, target repository, change, package revision, resolved branch/worktree). The transaction SHALL serialize only retries of the same managed change; it SHALL NOT block or interact with the start of a different managed change.

#### Scenario: Transaction precedes workspace mutation

- **WHEN** a managed start begins for change A in a multi-agent-profile checkout
- **THEN** a transaction record for change A is persisted before any worktree or board mutation occurs
- **AND** the transaction is retired only after the start completes successfully

#### Scenario: Unrelated managed changes start independently

- **GIVEN** a start transaction is active for change A
- **WHEN** a start begins for unrelated change B
- **THEN** change B's start proceeds without waiting on or being blocked by change A's transaction

#### Scenario: Interrupted start preserves its retry receipt

- **WHEN** a managed start for change A is interrupted before completion
- **THEN** change A's transaction record remains on disk
- **AND** a subsequent start for change A uses it to resume recovery rather than starting from an unrecorded state

### Requirement: Incomplete managed-start recovery is fenced to exact task identity

When a managed start finds transaction state without matching canonical OpenSpec provenance, the platform SHALL treat this as bounded incomplete creation state for that exact task and MAY recover it. Recovery SHALL act only on the worktree, branch and agent-board entry named by that task's own transaction, and SHALL refuse when the candidate has commits not reachable from the main branch, dirty paths not owned by that task, task-local state naming a different source issue or change, an ambiguous board match, or cannot be proven to be an exact registered Git worktree. Recovery SHALL NOT perform global worktree or board pruning.

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

