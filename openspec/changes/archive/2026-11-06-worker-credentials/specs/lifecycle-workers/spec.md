## ADDED Requirements

### Requirement: Workers resolve credentials through one placement-selected mechanism

Every job kind SHALL obtain its credentials through one resolver with no manual export. GitHub access SHALL use the active `gh` credential. With an enabled `[operator]` the Claude credential SHALL come only from `[independent_review.login.claude] token_file`; without it, only from the job's `CLAUDE_CODE_OAUTH_TOKEN`. Placement SHALL select the source, never which value is present.

#### Scenario: Review on the operator node without an export

- **GIVEN** an operator node with a valid token file and no exported token
- **WHEN** a worker probes Claude and runs a review
- **THEN** the probe and the reviewer are authenticated with the token file value

#### Scenario: Export does not replace a missing token file

- **GIVEN** an operator node without a valid token file and an exported token
- **WHEN** a worker needs the Claude credential
- **THEN** it fails naming the setting and the exported value is not used

#### Scenario: Hosted runner without the secret

- **GIVEN** a checkout without an enabled `[operator]` and no `CLAUDE_CODE_OAUTH_TOKEN`
- **WHEN** a worker needs the Claude credential
- **THEN** it fails naming the variable

#### Scenario: Kind that starts no provider

- **WHEN** a worker runs only finalize or post-merge kinds
- **THEN** it reads no Claude credential

### Requirement: The Claude credential reaches only LLM processes

The resolved Claude credential SHALL be present only in the environment of the readiness probe and of the LLM process, and never in harness Git or push environments, project checks, argv, logs or posted results.

#### Scenario: Finalize project checks

- **WHEN** a worker started with an exported token on the operator node runs project checks
- **THEN** the check environment does not contain the token

## MODIFIED Requirements

### Requirement: An ambient Claude OAuth token is removed

On a checkout with an enabled `[operator]`, any ambient `CLAUDE_CODE_OAUTH_TOKEN` SHALL be removed when the worker starts and before a sandboxed writer launches.

#### Scenario: Ambient token present

- **WHEN** an ambient `CLAUDE_CODE_OAUTH_TOKEN` is present on the operator node
- **THEN** it is removed
