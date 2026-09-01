## ADDED Requirements

### Requirement: Agent-facing instructions use bounded discoverable context pointers

Dev Platform SHALL keep always-on agent instruction surfaces bounded and SHALL provide explicit discoverable pointers to authoritative concern-specific guidance when additional detail is required.

#### Scenario: Task reaches a documented concern
- **WHEN** an agent task reaches a concern governed by detailed engineering guidance
- **THEN** an applicable always-on or tool-facing instruction identifies the authoritative destination or trigger path
- **AND** the agent does not depend on an unrelated duplicate copy of that policy

#### Scenario: Concern is irrelevant
- **WHEN** a task does not reach a concern governed by a detailed document
- **THEN** that detailed document is not required as universal always-on context solely for discoverability

### Requirement: Tool-specific instruction surfaces do not fork shared policy

Tool-specific instruction files SHALL reference shared Dev Platform rules rather than independently owning semantically equivalent workflow policy, except for bounded runtime-specific mechanics.

#### Scenario: Shared rule changes
- **WHEN** a shared lifecycle or safety rule changes
- **THEN** the authoritative shared source and rendered references remain coherent
- **AND** provider/runtime-specific files do not retain a conflicting copied version

### Requirement: Managed-task semantics are consistent across conversation surfaces

ChatGPT Project, Codex, and Claude SHALL preserve the same intent boundaries, canonical managed-task representation, source-of-truth model, and authoring STOP behavior even when their supported publication mechanics differ.

#### Scenario: ChatGPT Project fixes accepted work to Backlog
- **GIVEN** ChatGPT Project has connected GitHub mutation access but no target-repository checkout
- **WHEN** the user explicitly asks to record an accepted non-trivial change
- **THEN** ChatGPT can create or update exactly one Development Backlog Issue and one valid managed OpenSpec package using the canonical ChatGPT adapter contract
- **AND** the task remains in Backlog without implementation or managed start
- **AND** lack of local `managed_task.py` execution is not itself a blocker

#### Scenario: Repo-local agent fixes accepted work to Backlog
- **GIVEN** Codex or Claude operates inside a managed repository checkout with the platform authoring helper
- **WHEN** the user explicitly asks to record an accepted non-trivial change
- **THEN** the agent uses the supported deterministic `managed_task.py create --bundle ...` path
- **AND** does not manually reconstruct GitHub/package mechanics when the helper is available

### Requirement: Cross-surface authoring produces one consumable managed representation

A managed task authored from ChatGPT Project SHALL be consumable by the existing repository managed-task intake without a ChatGPT-specific import or translation layer.

#### Scenario: Coding agent later starts a ChatGPT-authored task
- **GIVEN** ChatGPT Project created a valid managed Development Backlog task and stopped
- **WHEN** Codex or Claude later runs the ordinary `start_managed_task.py owner/repo#N` flow
- **THEN** the package validates and materializes through the same intake contract as a repo-locally authored managed task
- **AND** repository-local OpenSpec becomes canonical after materialization
