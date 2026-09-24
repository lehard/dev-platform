# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Requirement board status is derived from terminal authority

The primary Requirement Project card SHALL reflect a recomputable projection of current orchestrator, child and shared-publication evidence. The Project field SHALL NOT become a second independent lifecycle.

#### Scenario: Execution is visible without premature completion

- **GIVEN** a Requirement has one or more linked children in progress or ready for shared integration
- **WHEN** its Project card is reconciled
- **THEN** the card shows a nonterminal execution stage
- **AND** no child receipt or handoff alone makes it Done

#### Scenario: Uncertain evidence fails closed

- **GIVEN** a required source is stale, missing, contradictory or explicitly blocked
- **WHEN** the board projection is computed
- **THEN** it reports blocked or unknown with a reason
- **AND** it does not optimistically write Ready or Done

#### Scenario: Protected publication permits Done

- **GIVEN** every required child is delivered and the exact shared candidate PR is merged with local main reconciled
- **WHEN** the Requirement card is reconciled
- **THEN** it reaches Done idempotently
- **AND** child Issues remain excluded from the primary human-facing view
