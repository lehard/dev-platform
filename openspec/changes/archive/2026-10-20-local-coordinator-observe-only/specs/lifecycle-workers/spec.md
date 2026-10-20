## ADDED Requirements

### Requirement: Harness candidate push uses the active gh credential

The deterministic harness push to a candidate or Requirement integration branch on a GitHub HTTPS origin SHALL authenticate with the active `gh` credential as reported by `gh auth token`, so an exported App installation token is used in CI and an ordinary operator login with write access is sufficient locally; it SHALL NOT require a coordinator-specific token. When `gh` reports no credential the push SHALL fail explicitly naming the missing `gh` credential, without echoing command output. The credential SHALL exist only in the environment of the single push process and SHALL NOT appear in argv, Git config files, writer checkouts or diagnostics.

#### Scenario: Local push without exported GH_TOKEN

- **GIVEN** an operator `gh` login and no exported `GH_TOKEN`
- **WHEN** the harness pushes a validated result to a candidate branch
- **THEN** the push authenticates with the operator credential
- **AND** the token is absent from argv, Git config and any error

#### Scenario: No gh credential

- **WHEN** `gh auth token` fails or prints nothing
- **THEN** the harness push fails naming the missing `gh` credential and nothing is pushed
