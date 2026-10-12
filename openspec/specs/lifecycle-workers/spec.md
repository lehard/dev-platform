# lifecycle-workers Specification

## Purpose
Let replaceable workers on any placement claim head-bound lifecycle jobs through one contract, while LLM processes hold no publication or repository credential and a deterministic harness performs the only validated, expected-head push.

## Requirements

### Requirement: Lifecycle work is published as head-bound jobs

The coordinator SHALL publish review, repair, integration-repair, finalize, retrospective, terminal-reconciliation and cleanup work as jobs bound to an exact candidate head, task-content identity and attempt. A job result for a different head SHALL be discarded.

#### Scenario: Candidate head moves while a job runs
- **WHEN** a worker returns a result for an older head
- **THEN** the result is discarded and the job is re-evaluated for the current head

### Requirement: Replaceable workers claim jobs through one contract

Workers SHALL claim jobs through one work-next contract with a head-bound, time-limited claim. At most one valid claim SHALL own a job; an expired or head-stale claim SHALL be reclaimable. Local, remote and hybrid placement SHALL differ only in where workers run and which job kinds they advertise.

#### Scenario: Two workers race
- **WHEN** two workers claim the same job
- **THEN** exactly one proceeds and the other abandons without side effects

#### Scenario: Worker dies
- **WHEN** a claim expires without a result
- **THEN** another worker can claim the job

### Requirement: LLM workers hold no publication or repository credential

An LLM process executing review, repair or integration-repair SHALL run without any GitHub, publication or repository credential and SHALL NOT have merge authority. Review SHALL be read-only. Any write result SHALL be validated by a deterministic harness — fast-forward from the expected head, within the candidate's scope, without workflow or lifecycle-evidence edits — and the harness SHALL perform the only push to that candidate branch with an expected-head guard.

#### Scenario: Repair touches a workflow file
- **WHEN** a repair result modifies a CI workflow or another candidate's paths
- **THEN** the harness rejects it and nothing is pushed

#### Scenario: Credential discovery attempt
- **WHEN** the LLM process inspects its environment
- **THEN** no GitHub token, credential helper or SSH agent is available

### Requirement: Workers select jobs by PR and by preflight-proven provider

A worker SHALL be able to restrict job selection to given PRs and to review and repair providers whose runtime passed a bounded readiness probe in the worker's own scratch environment, using the same login files the job would use. A job whose providers include no ready provider of the worker SHALL be skipped without a claim and SHALL NOT block jobs of other providers. A job carrying no resolved provider SHALL NOT be eligible for a provider-filtering worker. Unready providers and their limitations SHALL be reported. A worker that runs a repair job SHALL declare the provider of its writer command and SHALL fail explicitly when it does not. Without these options selection SHALL be unchanged.

#### Scenario: Unrunnable job at the lowest PR
- **GIVEN** the lowest-numbered claimable job names only a provider that fails preflight on this worker
- **AND** a higher-numbered job names a ready provider
- **WHEN** the worker selects with provider filtering
- **THEN** it claims the higher-numbered job and places no claim on the first

#### Scenario: Selection by PR
- **WHEN** the worker selects with a PR filter
- **THEN** only jobs of those PRs are considered

#### Scenario: Review uses the ready subset in job order
- **GIVEN** a review job names providers claude then codex and only codex is ready
- **WHEN** the worker runs it
- **THEN** the review runs on codex alone

#### Scenario: Repair without a declared provider
- **WHEN** a worker runs a repair job without declaring its writer provider
- **THEN** it fails explicitly before claiming

### Requirement: An unavailable writer runtime is not a failed repair

When a repair writer exits unsuccessfully or cannot start, the worker SHALL decide whether its provider runtime is usable with the same readiness probe. An unusable runtime SHALL be reported as unavailable with its limitation and SHALL NOT complete the job; a usable runtime SHALL keep the failure a real failed result.

#### Scenario: Writer cannot start
- **WHEN** the writer command cannot be executed
- **THEN** the outcome is unavailable naming the start failure and the job remains claimable

### Requirement: Worker claim identity is unique and validated

A lifecycle worker SHALL use exactly one worker identity for a run, and that identity SHALL appear unchanged in its claim records, result records and printed evidence. When no identity is supplied the worker SHALL generate one that includes a sanitized host name, the process id and a per-launch random nonce. An explicit identity (command-line option, otherwise the `DEV_PLATFORM_WORKER` variable) SHALL match `[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}` and an invalid explicit identity SHALL fail the run with a message naming the identity, before any claim or other GitHub write. No worker identity default constant SHALL exist in an executor interface.

#### Scenario: Generated identities do not collide

- **WHEN** two workers are launched with no explicit identity on different hosts, with the same process id, or successively with a reused process id
- **THEN** their generated identities differ and a claim by one is never treated as won by the other

#### Scenario: Explicit identity is used throughout

- **WHEN** an operator supplies a valid identity by option or variable
- **THEN** that identity is used for the claim, every result record and the printed result of the run, and the option takes precedence over the variable

#### Scenario: Invalid explicit identity fails

- **WHEN** the supplied identity is empty, longer than 64 characters or contains whitespace or a path separator
- **THEN** the worker exits non-zero naming the invalid identity, posts no comment and does not generate a replacement

#### Scenario: Earlier identities remain replayable

- **WHEN** lifecycle history contains a claim by a worker identity written before this contract
- **THEN** ownership replay still compares the recorded string exactly

### Requirement: Repair work runs only under the originating authorized provider

A repair or integration-repair job SHALL name exactly one provider. That provider SHALL be the provider of the originating task route recorded on the candidate handoff, unless an explicit recorded operator re-offer (a switch-provider event in the job record) or the operator provider switch recorded on the candidate names the job's provider, which then authorizes it; any other provider SHALL fail explicitly. An operator re-offer of a repair job SHALL name exactly one provider and SHALL be refused at command time otherwise, publishing nothing. The operator's switch (switch-provider, or resume with an explicit provider) SHALL be recorded on the candidate per job kind and SHALL persist, so later repair rounds and re-reviews of the candidate published without explicit providers run on the switched providers. When a worker passes both the executor provider and the BR-439 repair-provider readiness option they SHALL name the same provider, otherwise the worker SHALL exit non-zero before any GitHub call. A worker SHALL declare the provider of its executor, SHALL be offered and SHALL claim such a job only when the declared provider equals the recorded one, and SHALL record that provider in its claim and result. A job with a missing, empty, unknown or self-contradictory provider SHALL fail explicitly naming the pull request. An unauthorized worker SHALL leave the job claimable by a matching worker and report why it claimed nothing.

#### Scenario: Matching worker claims repair

- **WHEN** a repair job records provider `codex` and a worker declares provider `codex`
- **THEN** the worker claims the job and the claim and result records show provider `codex`

#### Scenario: Mismatched worker does not claim

- **WHEN** the same job is polled by a worker declaring provider `claude`
- **THEN** no claim comment is posted, the result reports the job as unauthorized for that provider and the job remains claimable by a matching worker

#### Scenario: Recorded operator switch authorizes another provider

- **WHEN** the originating route provider is `codex` and an operator re-offer recorded in the repair job switches it to `claude`
- **THEN** a worker declaring `claude` claims the job and records provider `claude`, a worker declaring `codex` is reported unauthorized, and a job naming `claude` without such a recorded re-offer, or with a re-offer naming another provider, fails explicitly naming the pull request

#### Scenario: Provider declaration required

- **WHEN** a worker advertising repair kinds is started without a provider declaration
- **THEN** it fails with a message naming the missing provider option and claims nothing

#### Scenario: Contradictory or missing route fails

- **WHEN** a repair job has no provider, an unsupported provider, or a provider that differs from its provider list
- **THEN** the operation fails explicitly and no job is claimed or executed under a default provider

#### Scenario: Operator switch persists into later rounds
- **WHEN** an operator switches a repair-pending candidate from `codex` to `claude`, and a later review finds material findings again
- **THEN** the next repair job names `claude` without a new re-offer, a re-review published without explicit providers follows the recorded review switch, and a switch naming two providers for a repair is refused publishing nothing

### Requirement: Trusted project checks run with an explicit project runtime

Trusted repository-owned project checks SHALL run in an environment built for that purpose, separate from the LLM and harness Git environments. The project SHALL declare required tools, required environment variable names and home-relative paths in its reviewed check configuration. The environment SHALL provide each declared tool on PATH, each required variable and each home path the operator has granted in a machine-local grant file located outside the checked checkout. GitHub and publication credentials, Git configuration injection, askpass helpers and the SSH agent SHALL be absent, and credential directories SHALL NOT be grantable. Any declared requirement that cannot be met SHALL fail explicitly naming it before the first check command runs. LLM and harness Git execution SHALL keep the credential-free scratch environment.

#### Scenario: Declared runtime is present

- **WHEN** a project declares Docker and uv as required tools, a required variable, and a home path that the operator granted
- **THEN** the project's checks see those tools, that variable and that path through the check HOME, and no GitHub token or SSH agent

#### Scenario: Missing declared input fails

- **WHEN** a declared tool is not on PATH, a declared variable is absent, or a declared home path is not granted
- **THEN** the run fails before any check command naming the missing input and no other runtime is substituted

#### Scenario: Credential exposure is refused

- **WHEN** a declaration or grant names a GitHub-credential variable, a credential directory such as `.ssh`, an absolute path or a path with a parent component, or the grant file is inside the checked checkout
- **THEN** the run fails explicitly naming the refused entry

#### Scenario: No declaration keeps isolation

- **WHEN** a project declares no runtime
- **THEN** its checks run in the existing scratch HOME with no granted paths

#### Scenario: LLM and harness Git stay credential-free

- **WHEN** an LLM worker or harness Git operation runs while a project runtime is declared and granted
- **THEN** its environment contains no GitHub credential and no granted home path and uses its scratch HOME

### Requirement: Coordinator logic is source-only and never a mandatory downstream dependency

The coordinator stack (`publication_queue`, `lifecycle_workers`, `pr_review_gate`) SHALL be loaded only after the committed contract selected coordinator mode. No entrypoint reachable from a generated downstream project (archive, finish, Requirement lifecycle, terminal reconciliation) SHALL import it at module level or require it to be present or enabled for portable behavior.

#### Scenario: Downstream entrypoints import without the coordinator stack
- **WHEN** `openspec_lifecycle`, `execute_requirement` and `requirement_terminal` are imported in a downstream-shaped checkout with the coordinator modules unimportable
- **THEN** the imports succeed and no coordinator module is loaded

#### Scenario: Coordinator mode loads the stack on demand
- **WHEN** the source contract selects coordinator mode for an archive
- **THEN** the coordinator modules are imported at that point and their failures surface unchanged

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

### Requirement: Enabled hosted workers start automatically from the queue and a backstop schedule

Once the hosted worker is delivered and configured, the hosted lifecycle worker workflow SHALL start without a manual command when the publication queue workflow completes and on a recurring schedule, in addition to manual dispatch. Every trigger SHALL run the workflow from the protected default branch under the same default-branch guard, and no step SHALL read the triggering event's payload. The installed Node runtime SHALL satisfy the engine range declared by the pinned Claude CLI.

#### Scenario: Queue completion starts a worker

- **WHEN** the publication queue workflow completes
- **THEN** a hosted worker run starts on the default branch without a manual command
- **AND** it claims a published review job if one is eligible, otherwise it reports the idle outcome

#### Scenario: Scheduled backstop

- **WHEN** the schedule fires
- **THEN** a hosted worker run starts on the default branch and handles any job whose event was missed or whose claim expired

#### Scenario: Triggering event payload is not used

- **WHEN** the triggering queue run came from a pull-request event
- **THEN** no workflow step reads a value from the triggering event's payload

#### Scenario: Supported runtime

- **WHEN** the review class installs the pinned Claude CLI
- **THEN** the installed Node major is within the CLI's declared engine range

#### Scenario: Triggers are removable

- **WHEN** the owner removes the `workflow_run` and `schedule` triggers
- **THEN** the hosted worker runs only on manual dispatch and the publication queue is unaffected
