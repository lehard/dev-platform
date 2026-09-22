# agent-instructions Specification Delta

## MODIFIED Requirements

### Requirement: Managed-task semantics are consistent across conversation surfaces

For an explicitly operator-integrated project, ChatGPT Project, Codex, and Claude SHALL preserve the same requirement-first intent boundaries, Requirement representation, source-of-truth model, and explicit direct-technical exception even when their supported publication mechanics differ. A portable project that does not select operator integration SHALL retain its self-contained local OpenSpec workflow.

#### Scenario: ChatGPT Project fixes accepted work to Backlog

- **GIVEN** an operator-integrated ChatGPT Project has connected GitHub mutation access but no target-repository checkout
- **WHEN** the user explicitly asks to record accepted non-trivial work
- **THEN** it creates or reuses exactly one `type:requirement` Development Backlog Issue through the canonical connected adapter and reads it back
- **AND** it stops without OpenSpec technical decomposition, managed start, or implementation

#### Scenario: Repo-local agent fixes accepted work to Backlog

- **GIVEN** Codex or Claude operates in an operator-integrated repository checkout
- **WHEN** the user explicitly asks to record accepted non-trivial work
- **THEN** it uses `requirement_intake.py create` and stops after the Requirement is durable

#### Scenario: Fresh execution and explicit technical work remain distinct

- **WHEN** an operator-integrated repository receives fresh non-trivial execution
- **THEN** it starts the Requirement, completes pre-authoring, links each internal child, and starts that child before implementation
- **AND** an explicitly supplied managed task or explicit technical authoring request preserves the existing managed-task path

#### Scenario: Quick work and portable work remain independent

- **WHEN** a request is a bounded quick task or the project has no operator-integration selection
- **THEN** it does not require an external Backlog or operator configuration
