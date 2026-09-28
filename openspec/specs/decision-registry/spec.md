# decision-registry Specification

## Purpose
Define how Dev Platform preserves consequential decision rationale, alternatives and revisit conditions across agent runtimes without replacing OpenSpec or work lifecycle authority.

## Requirements

### Requirement: Consequential decisions have a durable runtime-independent history

Dev Platform SHALL maintain a version-controlled repository decision registry that supported agent surfaces can discover without provider memory. A consequential record SHALL state its stable identity, scope, decision date and revision, accepted/current choice, rejected-for-now and deferred/watch alternatives where applicable, rationale, evidence links, revisit triggers, and supersession relationship. A later change SHALL create a new decision that links the earlier record and preserves the earlier rationale and evidence.

#### Scenario: Decision is reconsidered

- **GIVEN** an existing decision has new evidence or its revisit trigger fires
- **WHEN** the conclusion changes
- **THEN** a new record links and supersedes the earlier record
- **AND** the earlier rationale and evidence remain readable

### Requirement: Registry context does not compete with executable or work state

The decision registry SHALL provide historical rationale and SHALL NOT replace accepted OpenSpec behavior, active deltas, Business Requirements, backlog progress, or bounded task-local ADD evidence. Agents SHALL consult records relevant to the concern at hand without loading the whole registry into every prompt.

#### Scenario: Agent changes behavior governed by a decision

- **WHEN** an agent reaches that concern
- **THEN** it reads the relevant registry record for rationale and revisit conditions
- **AND** it uses OpenSpec and active deltas as the executable contract

### Requirement: TeamAI decision is the first representative record

The registry SHALL record that TeamAI stable v0.25.0 is not a Dev Platform production dependency or wholesale replacement, SHALL link the committed pilot evaluation, SHALL preserve candidates for selective substitution, and SHALL state evidence-based re-evaluation triggers including stable pinned distribution and ownership/rollback changes, stabilization of prerelease capabilities, and implementation of a reviewed/versioned/releasable Management Backend.

#### Scenario: Later agent asks why TeamAI is not adopted

- **WHEN** the agent reads the repository registry entry
- **THEN** it can identify the blocking mutable team-repo model, platform-owned surface collisions and uninstall/hook ownership problems
- **AND** it can identify candidate capabilities and concrete revisit conditions without relying on conversation memory
