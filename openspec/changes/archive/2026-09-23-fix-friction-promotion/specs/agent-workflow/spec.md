# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Platform friction promotion executes from a recorded event

The platform SHALL allow an operator to promote a recorded `scope=platform` friction event to the configured operator issue repository without a runtime configuration error. The promoted body SHALL retain the existing sanitized metadata and omit raw evidence.

#### Scenario: Operator dry-runs promotion

- **GIVEN** a recorded platform event and a configured promotion repository
- **WHEN** the operator runs `agent_friction.py promote <event> --dry-run`
- **THEN** the command exits successfully and prints the sanitized candidate with the source project identity
- **AND** no GitHub issue is created

#### Scenario: Promotion configuration is absent

- **WHEN** the operator runs promotion without `promotion.repo`
- **THEN** the command reports the missing operator setting before an issue mutation
