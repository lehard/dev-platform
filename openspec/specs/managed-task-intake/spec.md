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

