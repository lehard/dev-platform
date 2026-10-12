## ADDED Requirements

### Requirement: Hosted lifecycle workers run trusted code with class-scoped tokens

A GitHub-hosted workflow SHALL execute lifecycle workers using the same `work-next` claim, result and trust contract as any other placement. It SHALL run only code from the protected default branch on every trigger, SHALL NOT check out or execute pull-request-controlled content in any step of a job that holds a GitHub token, and SHALL obtain the PR head only through the worker harness into a disposable credential-free checkout. A job that holds a GitHub App token SHALL request a token limited to the current repository and to the permissions of its job-kind class (pull-request comments, plus contents write only for the harness push of review evidence or the finalization commit to the candidate branch), SHALL NOT request workflow, administration, actions or identity-token scopes, and SHALL NOT issue a merge request.

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

Hosted execution SHALL run only for job kinds named by an explicit repository setting, which is required configuration: when the workflow runs and the setting is unset or empty, the run SHALL fail explicitly naming the setting and SHALL run nothing. The hosted worker SHALL be off only because no automatic trigger exists, never because a setting is empty. An unknown kind SHALL fail the run naming it, and a kind without a hosted executor in this version (`repair`, `integration-repair`, `retrospective`, `terminal-reconciliation`, `cleanup`) SHALL be refused naming it and the basis (writer containment contract, or machine-local state and backlog access), staying on the local operator node. Before a class job runs any worker, a repository-owned hosted preflight SHALL prove the class and requested kinds, the presence of the provider secret (by presence flag only), that the Claude runtime passes the existing bounded readiness probe in the scratch environment a job would use, that a child process started through the credential-free environment sees no GitHub, App, askpass, SSH-agent or credential-helper credential, and that the token is an installation token scoped to exactly the current repository. The preflight SHALL stop at the first failed check with a non-zero exit and a diagnostic naming the missing or contradictory input or fixed category, SHALL print no credential value, and SHALL NOT substitute another strategy, provider, token or placement.

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

#### Scenario: Provider runtime or secret missing

- **WHEN** the provider secret flag is unset or the Claude readiness probe reports a limitation
- **THEN** the preflight exits non-zero naming the input or the limitation
- **AND** no job is claimed and no other provider or placement is tried

#### Scenario: Credential visible to a child

- **WHEN** the credential-boundary probe finds a GitHub, App, askpass, SSH-agent or credential-helper credential in the child environment
- **THEN** the preflight fails naming the category without printing any value

### Requirement: Hosted runs report concrete bounded outcomes

A hosted worker run SHALL print exactly one structured outcome distinguishing an idle run, a claimed job with its execution outcome, a provider reported unavailable with its limitation, and a refused or failed run with its cause. Provider, authentication, network, `gh` and check failures SHALL end the run unsuccessfully with the cause, SHALL leave the job claimable or in the existing bounded retry/blocked-escalation state, and SHALL NOT be reported as a completed job. A successful hosted run SHALL NOT assert that a candidate or Requirement is done.

#### Scenario: No claimable job

- **WHEN** no eligible job exists for the class
- **THEN** the run is successful, prints the idle outcome and makes no provider call

#### Scenario: Provider unavailable mid-job

- **WHEN** the review provider cannot start or authenticate after a claim
- **THEN** the run ends unsuccessfully naming the limitation
- **AND** the job is not recorded as completed and remains claimable or follows the existing bounded retry

#### Scenario: Rounds exhausted

- **WHEN** repair rounds are exhausted
- **THEN** the hosted worker performs no further automatic repair
- **AND** the candidate is in the existing blocked-escalation state with its supported human exit

### Requirement: Hosted triggers and restarts neither duplicate nor resurrect work

Once automatic triggers are enabled, hosted worker runs SHALL be serialised per class by a concurrency group that does not cancel a running worker, SHALL have a job timeout shorter than the claim lifetime, and SHALL use a worker identity unique to the run attempt and class that satisfies the worker identity contract. An overlapping or re-delivered trigger, a re-run, an expired claim, a changed PR head and an advanced `main` SHALL be handled by the existing head-bound claim and result rules: at most one valid claim owns a job, a result for a superseded head is discarded, an expired claim is reclaimable, and required checks are never bypassed.

#### Scenario: Two triggers at once

- **WHEN** the queue completion event and the schedule both start a worker for the same class
- **THEN** the runs do not execute concurrently
- **AND** at most one valid claim owns any job

#### Scenario: Run killed mid-job

- **WHEN** a hosted run is cancelled or times out after claiming
- **THEN** the claim expires after its lifetime and a later run reclaims the job
- **AND** no result is published for the abandoned attempt

#### Scenario: Head or main moves

- **WHEN** the PR head changes while a hosted job runs, or `main` advances before finalization
- **THEN** the old-head result is discarded and the job is re-evaluated for the current head
- **AND** the coordinator, not the hosted worker, prepares the candidate on the new `main`

### Requirement: Hosted enablement is a documented owner step that grants no new authority

The platform SHALL document, in one canonical engineering document, the ordered owner steps that enable the hosted worker (provider secret, enabling setting, manual run and its preflight outcome, then the automatic triggers through a reviewed change), the rollback, and the constraints a pilot must verify per job kind: provider runtime and credential availability, credential-boundary proof, token scope, duration, cost and limits, and failure behavior. A kind whose prerequisites cannot be proven SHALL stay off the hosted path with the local operator node as its recorded basis. The change SHALL introduce no second orchestrator, queue or state store, SHALL NOT make an agent enter or read a credential, and SHALL give no local worker merge authority beyond the existing CI-only protocol.

#### Scenario: Owner enables one class

- **WHEN** the owner follows the documented steps for the review class
- **THEN** a manual run reports the preflight outcome and either runs the worker or fails naming the missing input
- **AND** removing the automatic triggers turns the hosted worker off again

#### Scenario: Prerequisite unprovable

- **WHEN** a runtime, credential, containment or access prerequisite cannot be proven
- **THEN** the kind stays off the hosted path and is reported with the local operator node as its basis
- **AND** no kind is moved to CI by default

#### Scenario: No new authority

- **WHEN** the hosted worker or the document's fallback guidance is used
- **THEN** no worker gains merge or `main` authority beyond the existing CI-only protocol
