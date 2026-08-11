## ADDED Requirements

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
