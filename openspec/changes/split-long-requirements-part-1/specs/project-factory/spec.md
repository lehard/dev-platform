## MODIFIED Requirements

### Requirement: Generated agent guidance exposes one compact cross-agent task protocol

The Project Factory SHALL render one canonical vendor-neutral repository-wide entrypoint in `AGENTS.md` for discovering and safely entering the shared cross-agent task protocol.

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

### Requirement: Root AGENTS.md is a bounded navigation and invariant layer

Root `AGENTS.md` SHALL be a bounded always-on navigation and invariant layer rather than a complete duplicate of detailed workflow documentation.

#### Scenario: Root AGENTS.md is rendered

- **WHEN** the Project Factory renders root `AGENTS.md`
- **THEN** it is a bounded always-on navigation and invariant layer
- **AND** it is not a complete duplicate of detailed workflow documentation

### Requirement: Root AGENTS.md contains the always-on map and invariants

Root `AGENTS.md` SHALL contain the source-of-truth model, task-intent boundaries, safety/stop invariants required before further context can be loaded, canonical lifecycle entrypoints, platform/project ownership boundaries and stable repository-relative navigation to detailed guidance.

#### Scenario: Root AGENTS.md content

- **WHEN** the Project Factory renders root `AGENTS.md`
- **THEN** it contains the source-of-truth model, task-intent boundaries and safety/stop invariants required before further context can be loaded
- **AND** it contains canonical lifecycle entrypoints, platform/project ownership boundaries and stable repository-relative navigation to detailed guidance

### Requirement: Detailed workflow instructions live in thematic docs or mechanisms

Detailed managed-task, OpenSpec, worktree/publication, provider-routing, release, friction and other specialized workflow instructions SHALL live in canonical thematic repository docs or executable mechanisms and be loaded when relevant.

#### Scenario: Specialized workflow instructions are placed

- **WHEN** detailed managed-task, OpenSpec, worktree/publication, provider-routing, release, friction or other specialized workflow instructions are rendered
- **THEN** they live in canonical thematic repository docs or executable mechanisms
- **AND** they are loaded when relevant

### Requirement: Moving guidance detail keeps the underlying contracts

Moving detail out of root guidance SHALL NOT weaken or remove the underlying process, safety, verification or completion contracts.

#### Scenario: Detail is moved out of root guidance

- **WHEN** detail is moved out of root guidance
- **THEN** the underlying process, safety, verification and completion contracts are neither weakened nor removed

### Requirement: Tool-specific instruction files reference the canonical entrypoint

Tool-specific instruction files SHALL reference/import the canonical repository-wide entrypoint rather than fork its semantics.

#### Scenario: Tool-specific instruction file is rendered

- **WHEN** a tool-specific instruction file is rendered
- **THEN** it references/imports the canonical repository-wide entrypoint
- **AND** it does not fork the entrypoint's semantics

### Requirement: An additional agent shell needs no vendor-specific process contract

The platform SHALL NOT require a Hermes-specific or other vendor-specific parallel process contract merely to support an additional agent shell.

#### Scenario: Additional agent shell is supported

- **WHEN** the platform supports an additional agent shell such as Hermes
- **THEN** no Hermes-specific or other vendor-specific parallel process contract is required for that support

### Requirement: Guidance compaction is verified with focused evidence

Semantic-preserving compaction of the generated agent guidance SHALL be verified with focused structural, navigation, destination/link, render and semantic-preservation evidence.

#### Scenario: Semantic-preserving compaction is verified

- **WHEN** the generated agent guidance is compacted without changing its meaning
- **THEN** the compaction is verified with focused structural, navigation, destination/link, render and semantic-preservation evidence

### Requirement: Guidance compaction needs no unrelated full regression suite

Semantic-preserving compaction of the generated agent guidance SHALL NOT require an unrelated full software regression suite solely because instruction, documentation or template text changed.

#### Scenario: Only instruction text changed

- **WHEN** a semantic-preserving compaction changes only instruction, documentation or template text
- **THEN** an unrelated full software regression suite is not required solely because that text changed

### Requirement: Meaning-changing guidance compaction is reconciled with OpenSpec first

Where compaction intentionally changes directive meaning rather than only shortening or relocating it, the change SHALL be reconciled with OpenSpec first and SHALL carry targeted behavioral evidence for the affected surface.

#### Scenario: Compaction changes directive meaning

- **WHEN** a compaction intentionally changes directive meaning rather than only shortening or relocating it
- **THEN** the change is reconciled with OpenSpec first
- **AND** it carries targeted behavioral evidence for the affected surface
