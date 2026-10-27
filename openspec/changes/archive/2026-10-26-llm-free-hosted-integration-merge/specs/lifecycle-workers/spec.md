## MODIFIED Requirements

### Requirement: Hosted lifecycle workers run trusted code with class-scoped tokens

A GitHub-hosted workflow SHALL execute lifecycle workers using the same `work-next` claim, result and trust contract as any other placement. It SHALL run only code from the protected default branch on every trigger, SHALL NOT check out or execute pull-request-controlled content in any step of a job that holds a GitHub token, and SHALL obtain the PR head only through the worker harness into a disposable credential-free checkout. A job that holds a GitHub App token SHALL request a token limited to the current repository and to the permissions of its job-kind class (pull-request comments, plus contents write only for the harness push of review evidence, the finalization commit or the integration-merge commit to the candidate branch), SHALL NOT request workflow, administration, actions or identity-token scopes, and SHALL NOT issue a merge request.

#### Scenario: Allowed triggers

- **WHEN** the workflow is dispatched manually, or, once the owner has added them, the publication queue workflow completes or the schedule fires
- **THEN** the workflow runs the default-branch worker
- **AND** no pull-request or pull-request-target trigger exists and no pull-request-controlled file is executed while a token is held

#### Scenario: Shipped without automatic triggers

- **WHEN** the workflow is first delivered
- **THEN** it can be started only by manual dispatch and runs nothing on its own

#### Scenario: Class token rights

- **WHEN** a hosted class job creates its token
- **THEN** the token carries pull-request comment rights and contents write solely for the harness evidence push to the candidate branch
- **AND** it carries no workflow, administration, actions or identity-token scope

#### Scenario: No merge from a hosted worker

- **WHEN** a hosted worker runs any enabled kind to completion
- **THEN** it issues no pull-request merge request and leaves integration to the publication queue

### Requirement: Hosted execution requires explicit configuration and a passing evidence gate

Hosted execution SHALL run only for job kinds named by an explicit repository setting, which is required configuration: when the workflow runs and the setting is unset or empty, the run SHALL fail explicitly naming the setting and SHALL run nothing. The hosted worker SHALL be off only because no automatic trigger exists, never because a setting is empty. An unknown kind SHALL fail the run naming it, and a kind without a hosted executor in this version (`repair`, `integration-repair`, `retrospective`, `terminal-reconciliation`, `cleanup`) SHALL be refused naming it and the basis (writer containment contract, or machine-local state and backlog access), staying on the local operator node. The LLM-free `integration-merge` kind SHALL have a hosted executor in its own class that needs no provider secret, no LLM runtime and no `--llm-command`. Before a class job runs any worker, a repository-owned hosted preflight SHALL prove the class and requested kinds, the presence of the provider secret (by presence flag only), that the Claude runtime passes the existing bounded readiness probe in the scratch environment a job would use, that a child process started through the credential-free environment sees no GitHub, App, askpass, SSH-agent or credential-helper credential, and that the token is an installation token scoped to exactly the current repository. The preflight SHALL stop at the first failed check with a non-zero exit and a diagnostic naming the missing or contradictory input or fixed category, SHALL print no credential value, and SHALL NOT substitute another strategy, provider, token or placement.

#### Scenario: Required setting missing

- **WHEN** the workflow is run by hand and the enabling setting is unset or empty
- **THEN** the run fails naming the setting and starts no class job

#### Scenario: Unknown kind enabled

- **WHEN** the setting names a kind that is not a lifecycle job kind
- **THEN** the run fails naming that kind and no worker starts

#### Scenario: Kind without a hosted executor

- **WHEN** the setting names `repair`, `integration-repair`, `retrospective`, `terminal-reconciliation` or `cleanup`
- **THEN** the run is refused naming the kind and its basis
- **AND** no worker starts and the kind remains on the local operator node

#### Scenario: LLM-free integration merge enabled

- **WHEN** the setting names `integration-merge`
- **THEN** the plan has an integration class job for it that installs no LLM runtime and receives no provider secret
- **AND** its worker runs `work-next --kinds integration-merge --run` without `--llm-command`

#### Scenario: Provider runtime or secret missing

- **WHEN** the provider secret flag is unset or the Claude readiness probe reports a limitation
- **THEN** the preflight exits non-zero naming the input or the limitation
- **AND** no job is claimed and no other provider or placement is tried

#### Scenario: Credential visible to a child

- **WHEN** the credential-boundary probe finds a GitHub, App, askpass, SSH-agent or credential-helper credential in the child environment
- **THEN** the preflight fails naming the category without printing any value
