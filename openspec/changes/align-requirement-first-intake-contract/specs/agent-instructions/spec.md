# agent-instructions Specification Delta

## MODIFIED Requirements

### Requirement: Managed-task semantics are consistent across conversation surfaces

ChatGPT Project, Codex, and Claude SHALL preserve the same Discuss, generic Fix, non-trivial Execute, and explicit direct technical managed intent boundaries. Generic fixation SHALL create or reuse one human-facing Business Requirement without OpenSpec authoring; technical package publication belongs to subsequent requirement execution or explicit direct technical intent. Supported transport mechanics MAY differ without changing these meanings.

#### Scenario: ChatGPT Project fixes accepted work to Backlog

- **GIVEN** ChatGPT Project has connected GitHub mutation access but no checkout
- **WHEN** the user explicitly asks only to record accepted non-trivial work
- **THEN** ChatGPT creates or reuses and reads back exactly one `type:requirement` Business Requirement
- **AND** it creates no managed OpenSpec package or technical decomposition
- **AND** lack of local `requirement_intake.py` execution is not itself a blocker when the connected adapter verifies the same durable representation

#### Scenario: Repo-local agent fixes accepted work to Backlog

- **GIVEN** Codex or Claude operates inside a managed repository checkout
- **WHEN** the user explicitly asks only to record accepted non-trivial work
- **THEN** the agent uses `requirement_intake.py create` to create or reuse the Business Requirement and stops
- **AND** it does not invoke `managed_task.py create` for generic fixation

### Requirement: Cross-surface authoring produces one consumable managed representation

An internal or explicitly requested direct technical managed task authored from ChatGPT Project SHALL remain consumable by the ordinary managed-task intake without a ChatGPT-specific translation layer. A generic Business Requirement SHALL remain the same human-facing representation across conversation surfaces and SHALL not require a technical package.

#### Scenario: Coding agent later starts a ChatGPT-authored task

- **GIVEN** ChatGPT Project created a valid technical managed Development Backlog task under explicit technical intent or Requirement execution
- **WHEN** Codex or Claude later runs `start_managed_task.py owner/repo#N`
- **THEN** the package validates through the standard intake contract
- **AND** repository-local OpenSpec becomes canonical after materialization
