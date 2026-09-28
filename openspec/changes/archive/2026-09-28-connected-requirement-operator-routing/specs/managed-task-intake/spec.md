# managed-task-intake Specification Delta

## MODIFIED Requirements

### Requirement: Connected-GitHub authoring verifies durable managed state before reporting success

When a ChatGPT Project authors an internal or explicitly requested direct technical managed task through connected GitHub, it SHALL read back and verify the Issue, labels, and one active supported `managed-openspec:v1` package before reporting technical authoring success. Generic fixation through connected GitHub SHALL instead verify the durable Business Requirement representation, including exactly one configured `project:*` label and exactly one `priority:*` label, without requiring or publishing any managed OpenSpec package.

Connected Requirement routing SHALL come from the existing project/operator `[development_backlog]` configuration. It SHALL use the target repository's committed configuration when present. When the target intentionally does not track that configuration (an operator-managed repository), it SHALL use the operator-declared Project parameters rendered from that same configuration. Declared parameters that disagree with committed configuration SHALL be a conflict. The platform SHALL NOT introduce a second routing source or hardcode a concrete label, priority or operator configuration in public source.

#### Scenario: Connected authoring completes normally

- **WHEN** a ChatGPT Project records an accepted generic fixation request
- **THEN** it reads back the exact `type:requirement` Issue with business sections and target repository
- **AND** it verifies exactly the target's configured `project:*` label and one explicit or default `priority:*` label
- **AND** it reports successful fixation only after verifying that representation
- **AND** it does not publish a managed OpenSpec package or start execution

#### Scenario: Operator-managed target has no committed configuration

- **GIVEN** an operator-managed target such as Dev Platform keeps `.dev-platform.toml` untracked
- **AND** the ChatGPT Project declares Backlog repository, target repository, project label and default priority rendered by `requirement_intake.py routing-parameters`
- **WHEN** the ChatGPT Project records a Requirement for that target
- **THEN** it applies the declared project label and the explicit or default priority
- **AND** it reports success only after the same read-back verifies exactly those labels

#### Scenario: Connected Requirement routing cannot be resolved

- **WHEN** the target has no valid committed `[development_backlog]` and the declared Project parameters are missing, invalid, name another Backlog repository or another target
- **OR** declared parameters disagree with committed configuration
- **THEN** the adapter does not create a Requirement without verified project/priority metadata
- **AND** it reports the routing blocker

#### Scenario: Issue exists but package publication is incomplete

- **WHEN** an internal or explicitly requested direct technical managed task is authored through connected GitHub
- **THEN** the adapter reads back its exact Issue, configured labels, and one complete active `managed-openspec:v1` package
- **AND** it reports technical authoring success only after the existing package checks pass

#### Scenario: Partial state cannot be repaired safely

- **WHEN** connected technical authoring finds ambiguous or conflicting partial Issue/package state
- **THEN** it reports the exact blocker and does not claim technical authoring success
- **AND** it does not weaken managed-start validation or invent replacement product intent
