# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Requirement child execution uses bounded canonical context

Each internal Requirement child SHALL start or resume from its own materialized managed OpenSpec package, current repository state, and only explicit bounded dependency evidence. The Requirement supervisor SHALL NOT pass the accumulated pre-authoring transcript or unrelated sibling detail as child execution context.

#### Scenario: Child starts with canonical context

- **GIVEN** a linked child has an imported managed package and declared dependencies
- **WHEN** its execution handoff is assembled
- **THEN** the handoff identifies the exact child source and current repository revision
- **AND** it includes only the dependency receipts required for that child
- **AND** it excludes the pre-authoring transcript and unrelated sibling task bodies

#### Scenario: Dependency changes before resume

- **WHEN** a dependency receipt no longer matches canonical state
- **THEN** child execution stops on the stale handoff
- **AND** a fresh bounded handoff can be derived without recreating the child or trusting old transcript content

#### Scenario: Authored parent prose is not a canonical backlink

- **GIVEN** a child Issue describes a Parent Requirement in authored prose
- **WHEN** the managed adapter links or validates that child
- **THEN** it requires an exact canonical `Requirement: owner/repo#N` line and reciprocal parent listing
- **AND** a substring inside `Parent Requirement:` is not accepted as linkage evidence
