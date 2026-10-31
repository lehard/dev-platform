## MODIFIED Requirements

### Requirement: Managed-task semantics are consistent across conversation surfaces

For an explicitly operator-integrated project, ChatGPT Project, Codex, and Claude SHALL preserve the same Discuss, generic Fix, non-trivial Execute, and explicit direct technical managed intent boundaries. Supported transport mechanics MAY differ without changing these meanings.

#### Scenario: ChatGPT Project fixes accepted work to Backlog

- **GIVEN** an operator-integrated ChatGPT Project has connected GitHub mutation access but no target-repository checkout
- **WHEN** the user explicitly asks to record accepted non-trivial work
- **THEN** it creates or reuses exactly one `type:requirement` Development Backlog Issue through the canonical connected adapter and reads it back
- **AND** it stops without OpenSpec technical decomposition, managed start, or implementation
- **AND** lack of local `requirement_intake.py` execution is not itself a blocker when the connected adapter verifies the same durable representation

#### Scenario: Repo-local agent fixes accepted work to Backlog

- **GIVEN** Codex or Claude operates in an operator-integrated repository checkout
- **WHEN** the user explicitly asks to record accepted non-trivial work
- **THEN** it uses `requirement_intake.py create` and stops after the Requirement is durable
- **AND** it does not invoke `managed_task.py create` for generic fixation

#### Scenario: Fresh execution and explicit technical work remain distinct

- **WHEN** an operator-integrated repository receives fresh non-trivial execution
- **THEN** it starts the Requirement, completes pre-authoring, links each internal child, and starts that child before implementation
- **AND** an explicitly supplied managed task or explicit technical authoring request preserves the existing managed-task path

#### Scenario: Quick work and portable work remain independent

- **WHEN** a request is a bounded quick task or the project has no operator-integration selection
- **THEN** it does not require an external Backlog or operator configuration

### Requirement: Delivered documentation is navigable and self-contained for agents

A project rendered from the Dev Platform template SHALL include a documentation map reachable from its root `AGENTS.md` that states the roles of `AGENTS.md`, `docs/`, accepted OpenSpec specs, active OpenSpec changes and code and points to the canonical document for each concern.

#### Scenario: Agent looks for the right document

- **GIVEN** a freshly rendered project
- **WHEN** an agent follows the pointers from `AGENTS.md`
- **THEN** it reaches the docs map and from there the concern document, and every local link resolves

#### Scenario: Agent runs the OpenSpec lifecycle

- **WHEN** an agent reads the delivered OpenSpec guidance
- **THEN** it can identify each artifact's role and the Dev Platform entrypoints for start, verify and archive
- **AND** upstream OpenSpec documentation is described as supplementary, not required

## ADDED Requirements

### Requirement: Generic fixation creates only a Business Requirement

Generic fixation SHALL create or reuse one human-facing Business Requirement without OpenSpec authoring; technical package publication belongs to subsequent Requirement execution or explicit direct technical intent.

#### Scenario: Accepted work is fixed

- **WHEN** generic fixation is requested
- **THEN** one human-facing Business Requirement is created or reused without OpenSpec authoring
- **AND** technical package publication is left to subsequent Requirement execution or explicit direct technical intent

### Requirement: Portable projects keep their local OpenSpec workflow

A portable project that does not select operator integration SHALL retain its self-contained local OpenSpec workflow.

#### Scenario: Project does not select operator integration

- **GIVEN** a portable project that does not select operator integration
- **WHEN** work is executed in it
- **THEN** it uses its self-contained local OpenSpec workflow

### Requirement: Delivered OpenSpec guidance is self-contained

The OpenSpec guidance delivered to a project rendered from the Dev Platform template SHALL describe the artifact roles, accepted specs versus active delta, requirements and scenarios, contract change during implementation, semantic verification, archive, and the boundary between upstream OpenSpec and Dev Platform entrypoints, so that the standard lifecycle can be completed without external OpenSpec documentation.

#### Scenario: Agent completes the lifecycle from delivered guidance

- **GIVEN** a project rendered from the Dev Platform template
- **WHEN** an agent completes the standard OpenSpec lifecycle
- **THEN** the delivered OpenSpec guidance describes the artifact roles, accepted specs versus active delta, requirements and scenarios, contract change during implementation, semantic verification, archive, and the boundary between upstream OpenSpec and Dev Platform entrypoints
- **AND** no external OpenSpec documentation is required

### Requirement: Delivered root AGENTS.md remains a bounded map

The root `AGENTS.md` of a project rendered from the Dev Platform template SHALL remain a bounded map.

#### Scenario: Root AGENTS.md is rendered

- **WHEN** a project is rendered from the Dev Platform template
- **THEN** its root `AGENTS.md` is a bounded map
