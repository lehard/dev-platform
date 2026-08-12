## RENAMED Requirements

- FROM: `### Requirement: Generated agent guidance exposes one cross-agent task protocol`
- TO: `### Requirement: Generated agent guidance exposes one compact cross-agent task protocol`

## MODIFIED Requirements

### Requirement: Generated agent guidance exposes one compact cross-agent task protocol

The Project Factory SHALL render one canonical vendor-neutral repository-wide entrypoint in `AGENTS.md` for discovering and safely entering the shared cross-agent task protocol. Root `AGENTS.md` SHALL be a bounded always-on navigation and invariant layer rather than a complete duplicate of detailed workflow documentation. It SHALL contain the source-of-truth model, task-intent boundaries, safety/stop invariants required before further context can be loaded, canonical lifecycle entrypoints, platform/project ownership boundaries and stable repository-relative navigation to detailed guidance.

Detailed managed-task, OpenSpec, worktree/publication, provider-routing, release, friction and other specialized workflow instructions SHALL live in canonical thematic repository docs or executable mechanisms and be loaded when relevant. Moving detail out of root guidance SHALL NOT weaken or remove the underlying process, safety, verification or completion contracts.

Tool-specific instruction files SHALL reference/import the canonical repository-wide entrypoint rather than fork its semantics. The platform SHALL NOT require a Hermes-specific or other vendor-specific parallel process contract merely to support an additional agent shell.

Semantic-preserving compaction of this guidance SHALL be verified with focused structural, navigation, destination/link, render and semantic-preservation evidence. It SHALL NOT require an unrelated full software regression suite solely because instruction, documentation or template text changed. Where compaction intentionally changes directive meaning rather than only shortening or relocating it, the change SHALL be reconciled with OpenSpec first and SHALL carry targeted behavioral evidence for the affected surface.

#### Scenario: Repository supports Codex and Claude

- **WHEN** agent guidance is rendered for a repository supporting Codex, Claude or another compatible agent shell
- **THEN** `AGENTS.md` provides the same canonical repository-wide map and always-on invariants
- **AND** `CLAUDE.md` continues to import/reference `AGENTS.md`
- **AND** tool-specific platform-owned instruction files remain thin references/adapters instead of duplicate managed-task or lifecycle rule sets
- **AND** the repository does not require separate vendor-specific copies of the shared process contract

#### Scenario: Agent needs specialized workflow detail

- **WHEN** an agent reaches a managed-task, OpenSpec, worktree/publication, routing, friction or other specialized concern
- **THEN** root guidance provides a stable discoverable route to the canonical detailed repository guidance for that concern
- **AND** the detailed contract remains available without being embedded wholesale in the always-loaded root context

#### Scenario: Guidance is compacted

- **WHEN** platform guidance is reorganized to reduce root context
- **THEN** every meaningful process/safety directive is either retained as an always-on root invariant or moved to one canonical discoverable destination
- **AND** existing lifecycle, verification and completion semantics remain unchanged unless a separate approved OpenSpec delta explicitly changes them

#### Scenario: Desired behavior change is discovered

- **WHEN** directive meaning is intentionally changed rather than only shortened or relocated
- **THEN** the change is reconciled with OpenSpec before proceeding
- **AND** targeted behavioral evidence is required for the affected surface as applicable

#### Scenario: Instruction-only compaction is verified

- **WHEN** a change modifies only instruction, documentation or template text without changing executable behavior
- **THEN** verification uses focused structure, anchor, destination/link, render and semantic-preservation evidence
- **AND** an unrelated full software regression suite is not required solely because those file paths changed

## ADDED Requirements

### Requirement: Root agent guidance has a mechanically enforced context budget

The Project Factory SHALL enforce a bounded structural/size contract for platform-owned root agent guidance in central dogfood and rendered downstream output. The budget SHALL be small enough to prevent detailed specialized workflows from silently accumulating again and SHALL include required navigation/invariant anchors. A deliberate future increase SHALL require an explicit update to the contract or its tested configuration rather than incidental prose growth.

#### Scenario: Root guidance exceeds the approved budget

- **WHEN** a platform change makes central or rendered platform-owned root `AGENTS.md` exceed the configured hard budget
- **THEN** platform validation fails with an actionable indication that always-on context has grown beyond the approved boundary
- **AND** the change is not accepted merely because all moved text is individually valid guidance

#### Scenario: Required navigation anchor is removed

- **WHEN** root guidance no longer exposes a required source-of-truth, task-intent, safety/stop, lifecycle-entrypoint, ownership or detailed-guidance navigation category
- **THEN** the guidance contract test fails
- **AND** an agent is not expected to infer the missing contract from undocumented convention

#### Scenario: Platform renders supported profiles

- **WHEN** light, standard and multi-agent platform-owned profiles are rendered
- **THEN** each resulting root guidance file satisfies the bounded context contract
- **AND** profile-specific always-on safety requirements remain present without reintroducing full specialized workflow manuals
