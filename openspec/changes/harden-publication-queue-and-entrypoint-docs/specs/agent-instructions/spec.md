# agent-instructions Specification Delta

## ADDED Requirements

### Requirement: Documented entrypoint commands are accepted by their CLI

Every `orchestrate_pre_authoring.py` command line shown in the canonical and template agent-instruction and engineering-workflow surfaces SHALL be accepted by the current command-line parser. A documented command form that the CLI rejects SHALL be treated as a defect in the documentation or the CLI before release.

#### Scenario: Agent copies the documented pre-authoring status command

- **GIVEN** the canonical or template instructions document the pre-authoring status entrypoint
- **WHEN** the command is run as written with a requirement identity
- **THEN** the CLI accepts its arguments

#### Scenario: Documentation drifts from the CLI

- **WHEN** a documented pre-authoring command line no longer parses
- **THEN** the platform test suite fails
