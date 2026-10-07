## ADDED Requirements

### Requirement: LLM login is bound explicitly and per provider

The worker SHALL give an LLM CLI its own login only through an explicit binding: a file declared by `[independent_review.login.<provider>] token_file` in the platform configuration, or a file copied by `--llm-home-file`. A declared token file SHALL be a regular file with an absolute path (after home expansion) outside any git checkout, with no group or world permission bits, and non-empty; any violation SHALL fail explicitly naming the path and the rule and SHALL NOT include the file content. The token SHALL be injected only into the LLM environment of the declared provider. No credential-free environment, harness Git environment or push environment SHALL contain it, and an ambient `CLAUDE_CODE_OAUTH_TOKEN` SHALL NOT pass any credential-free environment.

#### Scenario: Declared token reaches only the provider's LLM environment

- **WHEN** the operator declares a valid `token_file` for `claude` and a review job runs with provider `claude`
- **THEN** the reviewer's environment carries the token as `CLAUDE_CODE_OAUTH_TOKEN`, and the harness Git, push and generic credential-free environments do not

#### Scenario: Ambient token is not passed implicitly

- **WHEN** `CLAUDE_CODE_OAUTH_TOKEN` is set in the worker's own environment and no `token_file` is declared
- **THEN** no environment built by the worker contains it

#### Scenario: Invalid token file fails without leaking

- **WHEN** the declared file is missing, empty, not a regular file, relative, readable by group or world, or inside a git checkout
- **THEN** the worker fails naming the path and the violated rule, and no output, comment or record contains the file content

#### Scenario: Home-file logins keep working

- **WHEN** a provider logs in through a file declared by `--llm-home-file` and no `token_file` is declared
- **THEN** the worker still runs that provider, subject to the login preflight

### Requirement: Login is proven before a review job is claimed

Before posting a claim for a review job under `--run`, the worker SHALL prove that each provider named by the job can log in, by running that provider's offline login probe in the scratch HOME and environment the reviewer will use. If any probe fails, times out or its binary is missing, the worker SHALL exit non-zero naming the provider and the available bindings, SHALL post no claim or result comment and SHALL NOT substitute another provider. A dry run SHALL NOT run the probe.

#### Scenario: Missing login fails before claim

- **WHEN** a review job names provider `claude` and the probe in the scratch HOME reports not logged in
- **THEN** the worker exits non-zero naming `claude` and both bindings, and no comment is posted on the pull request

#### Scenario: Working login proceeds unchanged

- **WHEN** every provider of the job passes its probe
- **THEN** the claim and execution proceed exactly as before

#### Scenario: Codex login is checked the same way

- **WHEN** a review job names provider `codex` and its probe reports not logged in
- **THEN** the worker fails before claiming exactly as for `claude`

#### Scenario: Preflight command reflects the worker

- **WHEN** an operator runs the independent-review preflight on a host whose scratch-HOME login is unavailable
- **THEN** its output reports the provider as not ready with the same cause and next step
