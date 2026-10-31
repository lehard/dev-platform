## MODIFIED Requirements

### Requirement: Workers select jobs by PR and by preflight-proven provider

A worker SHALL be able to restrict job selection to given PRs and to review and repair providers whose runtime passed a bounded readiness probe in the worker's own scratch environment, using the same login files the job would use. Without these options selection SHALL be unchanged.

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

### Requirement: Worker claim identity is unique and validated

A lifecycle worker SHALL use exactly one worker identity for a run, and that identity SHALL appear unchanged in its claim records, result records and printed evidence.

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

A repair or integration-repair job SHALL name exactly one provider.

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

Trusted repository-owned project checks SHALL run in an environment built for that purpose, separate from the LLM and harness Git environments.

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

### Requirement: Hosted lifecycle workers run trusted code with class-scoped tokens

A GitHub-hosted workflow SHALL execute lifecycle workers using the same `work-next` claim, result and trust contract as any other placement.

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

Hosted execution SHALL run only for job kinds named by an explicit repository setting, which is required configuration: when the workflow runs and the setting is unset or empty, the run SHALL fail explicitly naming the setting and SHALL run nothing.

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

### Requirement: Hosted runs report concrete bounded outcomes

A hosted worker run SHALL print exactly one structured outcome distinguishing an idle run, a claimed job with its execution outcome, a provider reported unavailable with its limitation, and a refused or failed run with its cause.

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

Once automatic triggers are enabled, hosted worker runs SHALL be serialised per class by a concurrency group that does not cancel a running worker, SHALL have a job timeout shorter than the claim lifetime, and SHALL use a worker identity unique to the run attempt and class that satisfies the worker identity contract.

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

The platform SHALL document, in one canonical engineering document, the ordered owner steps that enable the hosted worker (provider secret, enabling setting, manual run and its preflight outcome, then the automatic triggers through a reviewed change), the rollback, and the constraints a pilot must verify per job kind: provider runtime and credential availability, credential-boundary proof, token scope, duration, cost and limits, and failure behavior.

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

### Requirement: A sandboxed writer launch uses a platform-generated OS sandbox profile

The lifecycle harness SHALL provide a sandboxed writer launch that runs the LLM command under sandbox-runtime with a profile generated by platform code.

#### Scenario: Profile protects the integration checkout
- **GIVEN** an integration repository with a linked task worktree and a disposable writer checkout
- **WHEN** the harness generates the sandbox profile
- **THEN** only the disposable checkout, scratch home and writer tmp are writable
- **AND** the integration checkout, its common Git directory and every registered worktree are write-denied

#### Scenario: Unsupported platform
- **WHEN** a sandboxed writer launch is requested on a non-macOS platform
- **THEN** the launch fails before any process starts with an error naming the unproven platform

### Requirement: The Claude writer credential is scoped to the writer process

A sandboxed Claude writer SHALL receive `CLAUDE_CODE_OAUTH_TOKEN` only from the operator `[independent_review.login.claude] token_file`.

#### Scenario: Token stays out of the harness
- **WHEN** a sandboxed Claude writer is launched and its result is validated and pushed
- **THEN** the writer environment carries the token from the token file
- **AND** the harness Git and push environments and every recorded argument do not contain it

#### Scenario: Token file too open
- **WHEN** the token file mode grants group or other access
- **THEN** the launch is refused with an error naming the file and required mode

### Requirement: Harness candidate push uses the active gh credential

The deterministic harness push to a candidate or Requirement integration branch on a GitHub HTTPS origin SHALL authenticate with the active `gh` credential as reported by `gh auth token`, so an exported App installation token is used in CI and an ordinary operator login with write access is sufficient locally; it SHALL NOT require a coordinator-specific token.

#### Scenario: Local push without exported GH_TOKEN

- **GIVEN** an operator `gh` login and no exported `GH_TOKEN`
- **WHEN** the harness pushes a validated result to a candidate branch
- **THEN** the push authenticates with the operator credential
- **AND** the token is absent from argv, Git config and any error

#### Scenario: No gh credential

- **WHEN** `gh auth token` fails or prints nothing
- **THEN** the harness push fails naming the missing `gh` credential and nothing is pushed

### Requirement: Coordinator friction is attributed by public work identity

The coordinator friction sink SHALL attribute an event to the Requirement through the public work identity encoded in the managed candidate branch (`BR-N` for the Requirement, `BR-N/TM` for a child), derived without reading runner configuration, the Development Backlog or any other source.

#### Scenario: Hosted review with material findings records friction
- **GIVEN** a managed candidate and a hosted contract without Development Backlog configuration
- **WHEN** a hosted review finds material findings
- **THEN** one run records `repair-pending` and a trusted coordinator evidence record bound to the Requirement's work identity
- **AND** no further review round or evidence commit is created

#### Scenario: Malformed managed branch
- **WHEN** friction must be recorded for a candidate whose branch looks managed but carries a malformed identity
- **THEN** recording fails with an error naming the branch
- **AND** no transition is published without durable friction

### Requirement: Content-bound gates survive trusted harness pushes

Gates bound to task-content identity SHALL remain valid on a head reached through a trusted harness push of the same candidate when the task-content digest is unchanged, including when an interrupted job is recovered from its validated-push receipt and when the next job claims that head.

#### Scenario: Review without material findings keeps admission gates
- **WHEN** a hosted review without material findings pushes its evidence and records `finalize-pending`
- **THEN** the record carries the admission gates `semantic-verification`, `selected-checks` and `developer-friction` with the review gate
- **AND** a later finalize job with an unchanged content digest does not require fresh semantic verification

#### Scenario: Restoring gates lost before the fix
- **GIVEN** a `finalize-pending` candidate whose admission gates were lost across trusted review-evidence pushes with an unchanged content digest
- **WHEN** the operator runs the restore command
- **THEN** one record on the current head carries the restored gates and the state is unchanged

#### Scenario: Restoration across a foreign push
- **WHEN** any head move between the gated record and the current head lacks a trusted harness push receipt or changed the content digest
- **THEN** the restore command refuses, naming that head move, and publishes nothing

### Requirement: The hosted pilot ends in a recorded placement decision

A bounded pilot on real pull requests of the platform repository SHALL end in a durable record of, for each hosted lifecycle job kind, whether it runs hosted or remains on the local fallback, with the verified constraints behind the decision: provider runtime and credential availability, credential-boundary proof, token scope, observed duration, cost and limits, and failure behavior.

#### Scenario: Prerequisite proven

- **WHEN** a kind's preflight and a real-PR run succeed
- **THEN** the record states it as hosted with the observed constraints

#### Scenario: Prerequisite unprovable

- **WHEN** a runtime, credential, containment or access prerequisite cannot be proven
- **THEN** the record keeps the kind off the hosted path and names the basis for the local operator node
- **AND** no kind is moved to CI by default

#### Scenario: Value not observable

- **WHEN** a constraint such as per-job provider cost cannot be observed
- **THEN** the record marks it unobserved with the reason instead of an estimate

#### Scenario: Local fallback is not widened

- **WHEN** the record recommends the local fallback for a kind
- **THEN** it grants that worker no merge or `main` authority beyond the existing CI-only protocol

### Requirement: Workers read unchanged GitHub state through the disposable read cache

Lifecycle workers SHALL read PR lists, PR comment histories and Requirement Issue state through the same disposable local read cache as the lifecycle overview, so unchanged reads are revalidated conditionally instead of re-fetched.

#### Scenario: Worker poll with nothing changed
- **GIVEN** a warm cache and no change on GitHub
- **WHEN** a worker polls for its next job
- **THEN** it selects the same job as a cache-free poll
- **AND** it spends conditional requests rather than counted re-reads for unchanged PRs

#### Scenario: Corrupt cache stops the worker
- **WHEN** the cache file is corrupt
- **THEN** the worker run fails naming the file and the reset command and claims nothing

### Requirement: Post-merge lifecycle work runs on the operator Mac on a schedule

The platform SHALL provide a scheduled operator-Mac runner that executes the existing retrospective, terminal-reconciliation and cleanup jobs through `lifecycle_workers.py work-next --run` and its claim/result protocol, with no queue, claim format or state store of its own.

#### Scenario: Chain caught up in one round
- **GIVEN** merged PRs whose retrospective, terminal-reconciliation and cleanup are pending
- **WHEN** a round runs
- **THEN** it repeats `work-next` so each next job of the chain is claimed and executed until `work-next` reports idle or a bound is reached
- **AND** each run appears in the journal with PR, kind, status, outcome and duration

#### Scenario: Low REST remainder
- **WHEN** the GitHub REST remainder is below the threshold at the start of a round or between runs
- **THEN** the round claims nothing further and records a skip with the remainder and reset time
- **AND** the process exits successfully

#### Scenario: Two rounds overlap
- **WHEN** a round starts while another round holds the single-instance lock
- **THEN** it records `previous round still running` and runs nothing

#### Scenario: Round killed or machine rebooted
- **WHEN** a round dies after claiming a job
- **THEN** no result is published for it and its claim expires by the claim protocol
- **AND** the next round journals the interrupted round and the job becomes claimable again without a duplicate valid claim

#### Scenario: A job keeps failing
- **WHEN** a post-merge job fails in successive rounds until the platform attempt limit is spent
- **THEN** the existing post-merge attention is posted on the merged PR and shown by the lifecycle overview
- **AND** the runner never retries within a round or with another strategy

#### Scenario: Blocked obligation waits for the next round
- **GIVEN** a round in which PR A's cleanup ends `blocked` and PR B has a pending post-merge job
- **WHEN** the round continues
- **THEN** further `work-next` runs of that round exclude PR A and PR B's job is still claimed and executed
- **AND** PR A's next attempt happens in a later round

#### Scenario: Process-check tool missing
- **WHEN** `lsof` does not resolve on the runner's PATH
- **THEN** the round ends `failed` naming the tool before any job is claimed and no attempt of any obligation is spent

#### Scenario: Missing configuration
- **WHEN** a required argument, the `gh` credential or the journal directory is missing or invalid
- **THEN** the runner exits non-zero naming it and runs nothing

### Requirement: Post-merge environment defects spend no obligation attempt

When a claimed post-merge job cannot run because the executing environment is defective — the cleanup's active-process check is unavailable — the executor SHALL NOT post a `blocked` or `failed` result receipt for the job.

#### Scenario: Process check unavailable after claim
- **WHEN** a claimed cleanup job meets `process-check-unavailable`
- **THEN** no result receipt is posted for that job, its claim is released and `work-next` exits non-zero naming the defect
- **AND** the next derivation offers the same attempt again

#### Scenario: Worktree already gone
- **WHEN** a cleanup job runs and no worktree of the task branch exists
- **THEN** the job posts `already-clean` and the cleanup obligation is complete

### Requirement: An exhausted post-merge obligation can be re-offered with a fresh budget

Post-merge derivation SHALL read an operator re-offer sequence from the merged candidate's latest exact-head coordinator record (`attempts["post-merge-reoffers"]`, with the re-offer event carried in its `next_job`).

#### Scenario: Re-offered cleanup
- **GIVEN** a merged PR whose retrospective and terminal reconciliation completed and whose cleanup exhausted its attempts
- **WHEN** a re-offer record with sequence 1 is published
- **THEN** the next post-merge job is cleanup attempt 0 under the sequence-1 job id
- **AND** retrospective and terminal reconciliation are not offered again

### Requirement: Post-merge obligations are discovered beyond the recent-closed window

Lifecycle workers SHALL consider as merged candidates, in addition to the bounded page of most recently updated closed PRs, every closed PR carrying the coordinator's `lifecycle:merged` label that is not labeled `post-merge:settled`, read from a complete paginated listing.

#### Scenario: Open obligation outside the recent window
- **GIVEN** a coordinator-merged PR with an open post-merge obligation that is not among the 50 most recently updated closed PRs
- **WHEN** `work-next` with post-merge kinds runs, or the lifecycle overview is built
- **THEN** the obligation is offered by the worker and the PR is shown by the overview

#### Scenario: Settled chain stops being re-read
- **WHEN** `work-next` derives a merged PR whose post-merge chain has no next job and no exhausted obligation
- **THEN** it labels the PR `post-merge:settled`
- **AND** later discovery does not read it outside the recent window
- **AND** a PR with an open or exhausted obligation is never labeled

#### Scenario: Dry run writes nothing
- **WHEN** `work-next --dry-run` derives a settled merged PR
- **THEN** no label is written

#### Scenario: Unreadable candidate source
- **WHEN** a page of the open-PR listing, the recent-closed page or the `lifecycle:merged` label listing cannot be read
- **THEN** the command fails naming the read
- **AND** it does not report idle or a partial candidate set

#### Scenario: Selecting one old merged PR
- **WHEN** `work-next --pr N` names a merged PR outside the recent window
- **THEN** PR N is read directly and its post-merge job is offered when one is open

### Requirement: A post-merge job released to the limit raises attention

When the next post-merge job of a merged PR (retrospective, terminal reconciliation or cleanup) has been released after failed runs `MAX_RELEASES` times, derivation SHALL offer no job for it and SHALL report the obligation as exhausted with a reason naming the kind, the release count and the last release cause.

#### Scenario: Third release of a post-merge job
- **GIVEN** a merged PR whose retrospective job was released twice
- **WHEN** a third run of that job fails and releases its claim
- **THEN** the attention comment is posted on the merged PR with the release count and the last cause
- **AND** derivation offers no job and reports the retrospective as exhausted
- **AND** no `blocked-escalation` record is published

#### Scenario: Below the limit
- **WHEN** the next post-merge job was released fewer than `MAX_RELEASES` times
- **THEN** it is still offered and no attention is posted

#### Scenario: Re-offer after release exhaustion
- **WHEN** the operator re-offers the exhausted obligation with `reoffer-post-merge`
- **THEN** the obligation is offered again under the re-offer's job ids with no releases counted

#### Scenario: Pre-merge job unchanged
- **WHEN** a pre-merge job is released `MAX_RELEASES` times
- **THEN** the candidate moves to `blocked-escalation` as before

## ADDED Requirements

### Requirement: A job with no ready provider of the worker is skipped without a claim

A job whose providers include no ready provider of the worker SHALL be skipped without a claim and SHALL NOT block jobs of other providers.

#### Scenario: No provider of the job is ready for the worker

- **WHEN** a job's providers include no ready provider of the worker
- **THEN** the job is skipped without a claim
- **AND** jobs of other providers are not blocked

### Requirement: A job without a resolved provider is ineligible for a provider-filtering worker

A job carrying no resolved provider SHALL NOT be eligible for a provider-filtering worker.

#### Scenario: Job carries no resolved provider

- **GIVEN** a provider-filtering worker
- **WHEN** a job carries no resolved provider
- **THEN** the job is not eligible for that worker

### Requirement: Unready providers are reported with their limitations

Unready providers and their limitations SHALL be reported.

#### Scenario: A provider is not ready

- **WHEN** a provider is unready
- **THEN** the unready provider and its limitations are reported

### Requirement: A repair worker declares the provider of its writer command

A worker that runs a repair job SHALL declare the provider of its writer command and SHALL fail explicitly when it does not.

#### Scenario: Repair worker without a declared writer provider

- **WHEN** a worker that runs a repair job does not declare the provider of its writer command
- **THEN** the worker fails explicitly

### Requirement: A worker without a supplied identity generates a unique identity

When no worker identity is supplied the lifecycle worker SHALL generate a worker identity that includes a sanitized host name, the process id and a per-launch random nonce.

#### Scenario: No identity supplied

- **WHEN** a lifecycle worker starts with no worker identity supplied
- **THEN** it generates a worker identity that includes a sanitized host name, the process id and a per-launch random nonce

### Requirement: An explicit worker identity is validated before any GitHub write

An explicit worker identity (command-line option, otherwise the `DEV_PLATFORM_WORKER` variable) SHALL match `[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}` and an invalid explicit worker identity SHALL fail the run with a message naming the identity, before any claim or other GitHub write.

#### Scenario: Invalid explicit identity

- **WHEN** an explicit worker identity from the command-line option, otherwise the `DEV_PLATFORM_WORKER` variable, does not match `[A-Za-z0-9][A-Za-z0-9._:@-]{0,63}`
- **THEN** the run fails with a message naming the identity
- **AND** no claim or other GitHub write happens

### Requirement: Executor interfaces carry no worker identity default

No worker identity default constant SHALL exist in an executor interface.

#### Scenario: Executor interface defines no identity default

- **WHEN** an executor interface is defined
- **THEN** it contains no worker identity default constant

### Requirement: A repair job's provider is the originating route provider unless an operator switch authorizes another

The provider named by a repair or integration-repair job SHALL be the provider of the originating task route recorded on the candidate handoff, unless an explicit recorded operator re-offer (a switch-provider event in the job record) or the operator provider switch recorded on the candidate names the job's provider, which then authorizes it; any other provider SHALL fail explicitly.

#### Scenario: Provider differs from the originating route without an operator switch

- **WHEN** a repair or integration-repair job names a provider other than the provider of the originating task route recorded on the candidate handoff
- **AND** neither an explicit recorded operator re-offer (a switch-provider event in the job record) nor the operator provider switch recorded on the candidate names that provider
- **THEN** the job fails explicitly

#### Scenario: An operator switch names the job's provider

- **WHEN** an explicit recorded operator re-offer or the operator provider switch recorded on the candidate names the job's provider
- **THEN** that provider is authorized for the job

### Requirement: An operator re-offer of a repair job names exactly one provider

An operator re-offer of a repair job SHALL name exactly one provider and SHALL be refused at command time otherwise, publishing nothing.

#### Scenario: Re-offer without exactly one provider

- **WHEN** an operator re-offer of a repair job does not name exactly one provider
- **THEN** it is refused at command time
- **AND** nothing is published

### Requirement: The operator provider switch persists on the candidate per job kind

The operator's provider switch (switch-provider, or resume with an explicit provider) SHALL be recorded on the candidate per job kind and SHALL persist, so later repair rounds and re-reviews of the candidate published without explicit providers run on the switched providers.

#### Scenario: Later rounds after a switch

- **GIVEN** the operator switched the provider through switch-provider, or resume with an explicit provider
- **WHEN** later repair rounds and re-reviews of the candidate are published without explicit providers
- **THEN** the switch is recorded on the candidate per job kind and persists
- **AND** those rounds and re-reviews run on the switched providers

### Requirement: A worker's executor and repair-readiness providers must agree

When a worker passes both the executor provider and the BR-439 repair-provider readiness option, the executor provider and the readiness option SHALL name the same provider, otherwise the worker SHALL exit non-zero before any GitHub call.

#### Scenario: Executor and readiness providers differ

- **WHEN** a worker passes both the executor provider and the BR-439 repair-provider readiness option naming different providers
- **THEN** the worker exits non-zero before any GitHub call

### Requirement: A worker claims a repair job only under the recorded provider

A worker SHALL declare the provider of its executor, SHALL be offered and SHALL claim a repair or integration-repair job only when the declared provider equals the recorded provider, and SHALL record that provider in its claim and result.

#### Scenario: Declared provider equals the recorded provider

- **WHEN** a worker declares the provider of its executor and it equals the provider recorded for a repair or integration-repair job
- **THEN** the worker is offered and claims the job
- **AND** it records that provider in its claim and result

#### Scenario: Declared provider differs

- **WHEN** the declared provider differs from the recorded provider
- **THEN** the worker is not offered and does not claim the job

### Requirement: A job with an invalid provider fails naming the pull request

A job with a missing, empty, unknown or self-contradictory provider SHALL fail explicitly naming the pull request.

#### Scenario: Provider missing or contradictory

- **WHEN** a job has a missing, empty, unknown or self-contradictory provider
- **THEN** it fails explicitly naming the pull request

### Requirement: An unauthorized worker leaves a repair job claimable

An unauthorized worker SHALL leave a repair or integration-repair job claimable by a matching worker and report why it claimed nothing.

#### Scenario: Worker not authorized for the job

- **WHEN** a worker is not authorized for a repair or integration-repair job
- **THEN** the job stays claimable by a matching worker
- **AND** the worker reports why it claimed nothing

### Requirement: A project declares its check runtime requirements

The project SHALL declare required tools, required environment variable names and home-relative paths in its reviewed check configuration.

#### Scenario: Project declares runtime needs

- **WHEN** a project needs tools, environment variables or home paths for its trusted checks
- **THEN** it declares the required tools, required environment variable names and home-relative paths in its reviewed check configuration

### Requirement: The project check environment provides declared and granted requirements

The trusted project check environment SHALL provide each declared tool on PATH, each required variable and each home path the operator has granted in a machine-local grant file located outside the checked checkout.

#### Scenario: Declared requirements are provided

- **WHEN** trusted project checks run
- **THEN** each declared tool is on PATH and each required variable is provided
- **AND** each home path the operator has granted in a machine-local grant file located outside the checked checkout is provided

### Requirement: The project check environment carries no credentials

In the trusted project check environment, GitHub and publication credentials, Git configuration injection, askpass helpers and the SSH agent SHALL be absent, and credential directories SHALL NOT be grantable.

#### Scenario: Credentials are absent from project checks

- **WHEN** trusted project checks run
- **THEN** GitHub and publication credentials, Git configuration injection, askpass helpers and the SSH agent are absent
- **AND** a credential directory cannot be granted

### Requirement: An unmet declared check requirement fails before checks run

Any declared requirement that cannot be met SHALL fail explicitly naming the requirement before the first check command runs.

#### Scenario: A declared requirement cannot be met

- **WHEN** a declared requirement cannot be met
- **THEN** the run fails explicitly naming the requirement
- **AND** no check command has run

### Requirement: LLM and harness Git execution keep the credential-free scratch environment

LLM and harness Git execution SHALL keep the credential-free scratch environment.

#### Scenario: LLM or harness Git command runs

- **WHEN** an LLM or harness Git command runs
- **THEN** it runs in the credential-free scratch environment

### Requirement: A hosted worker workflow runs only default-branch code

A GitHub-hosted workflow that executes lifecycle workers SHALL run only code from the protected default branch on every trigger, SHALL NOT check out or execute pull-request-controlled content in any step of a job that holds a GitHub token, and SHALL obtain the PR head only through the worker harness into a disposable credential-free checkout.

#### Scenario: Hosted workflow is triggered

- **WHEN** the GitHub-hosted lifecycle worker workflow runs on any trigger
- **THEN** it runs only code from the protected default branch
- **AND** no step of a job that holds a GitHub token checks out or executes pull-request-controlled content
- **AND** the PR head is obtained only through the worker harness into a disposable credential-free checkout

### Requirement: A hosted job requests only a class-scoped App token

A job that holds a GitHub App token SHALL request a token limited to the current repository and to the permissions of its job-kind class (pull-request comments, plus contents write only for the harness push of review evidence, the finalization commit or the integration-merge commit to the candidate branch), SHALL NOT request workflow, administration, actions or identity-token scopes, and SHALL NOT issue a merge request.

#### Scenario: Job requests its App token

- **WHEN** a job that holds a GitHub App token requests the token
- **THEN** the token is limited to the current repository and to the permissions of its job-kind class
- **AND** no workflow, administration, actions or identity-token scope is requested
- **AND** the job issues no merge request

### Requirement: The hosted worker is off only through the absence of automatic triggers

The hosted worker SHALL be off only because no automatic trigger exists, never because a setting is empty.

#### Scenario: Hosted worker is off

- **WHEN** the hosted worker is off
- **THEN** it is off because no automatic trigger exists
- **AND** not because a setting is empty

### Requirement: An unknown hosted job kind fails the run

An unknown job kind SHALL fail the run naming the kind.

#### Scenario: Setting names an unknown kind

- **WHEN** an unknown job kind is requested
- **THEN** the run fails naming the kind

### Requirement: A job kind without a hosted executor is refused and stays local

A job kind without a hosted executor in this version (`repair`, `integration-repair`, `retrospective`, `terminal-reconciliation`, `cleanup`) SHALL be refused naming the kind and the basis (writer containment contract, or machine-local state and backlog access), staying on the local operator node.

#### Scenario: Kind without hosted executor is requested

- **WHEN** a kind without a hosted executor in this version (`repair`, `integration-repair`, `retrospective`, `terminal-reconciliation`, `cleanup`) is requested
- **THEN** it is refused naming the kind and the basis (writer containment contract, or machine-local state and backlog access)
- **AND** the kind stays on the local operator node

### Requirement: The integration-merge kind has an LLM-free hosted executor

The LLM-free `integration-merge` kind SHALL have a hosted executor in its own class that needs no provider secret, no LLM runtime and no `--llm-command`.

#### Scenario: Hosted integration-merge

- **WHEN** the `integration-merge` kind runs hosted
- **THEN** it runs in its own class
- **AND** it needs no provider secret, no LLM runtime and no `--llm-command`

### Requirement: A hosted preflight proves class, secret and runtime readiness before any worker runs

Before a class job runs any worker, a repository-owned hosted preflight SHALL prove the class and requested kinds, the presence of the provider secret (by presence flag only), and that the Claude runtime passes the existing bounded readiness probe in the scratch environment a job would use.

#### Scenario: Class job starts

- **WHEN** a class job is about to run a worker
- **THEN** the repository-owned hosted preflight proves the class and requested kinds and the presence of the provider secret by presence flag only
- **AND** it proves that the Claude runtime passes the existing bounded readiness probe in the scratch environment a job would use

### Requirement: A hosted preflight proves the credential boundary and token scope before any worker runs

Before a class job runs any worker, a repository-owned hosted preflight SHALL prove that a child process started through the credential-free environment sees no GitHub, App, askpass, SSH-agent or credential-helper credential, and that the token is an installation token scoped to exactly the current repository.

#### Scenario: Class job starts with a token

- **WHEN** a class job is about to run a worker
- **THEN** the repository-owned hosted preflight proves that a child process started through the credential-free environment sees no GitHub, App, askpass, SSH-agent or credential-helper credential
- **AND** it proves that the token is an installation token scoped to exactly the current repository

### Requirement: The hosted preflight stops at the first failed check without substitution

The repository-owned hosted preflight SHALL stop at the first failed check with a non-zero exit and a diagnostic naming the missing or contradictory input or fixed category, SHALL print no credential value, and SHALL NOT substitute another strategy, provider, token or placement.

#### Scenario: A preflight check fails

- **WHEN** a hosted preflight check fails
- **THEN** the preflight stops with a non-zero exit and a diagnostic naming the missing or contradictory input or fixed category
- **AND** no credential value is printed
- **AND** no other strategy, provider, token or placement is substituted

### Requirement: Hosted run failures end the run unsuccessfully without completing the job

Provider, authentication, network, `gh` and check failures SHALL end the hosted worker run unsuccessfully with the cause, SHALL leave the job claimable or in the existing bounded retry/blocked-escalation state, and SHALL NOT be reported as a completed job.

#### Scenario: Hosted run hits a provider or check failure

- **WHEN** a provider, authentication, network, `gh` or check failure occurs in a hosted worker run
- **THEN** the run ends unsuccessfully with the cause
- **AND** the job stays claimable or in the existing bounded retry/blocked-escalation state
- **AND** the failure is not reported as a completed job

### Requirement: A successful hosted run does not assert completion

A successful hosted run SHALL NOT assert that a candidate or Requirement is done.

#### Scenario: Hosted run succeeds

- **WHEN** a hosted run succeeds
- **THEN** it does not assert that a candidate or Requirement is done

### Requirement: Re-delivered triggers and restarts follow the head-bound claim rules

An overlapping or re-delivered trigger, a re-run, an expired claim, a changed PR head and an advanced `main` SHALL be handled by the existing head-bound claim and result rules: at most one valid claim owns a job, a result for a superseded head is discarded, an expired claim is reclaimable, and required checks are never bypassed.

#### Scenario: Trigger overlaps or the head moves

- **WHEN** an overlapping or re-delivered trigger, a re-run, an expired claim, a changed PR head or an advanced `main` occurs
- **THEN** the existing head-bound claim and result rules handle it
- **AND** at most one valid claim owns a job and a result for a superseded head is discarded
- **AND** an expired claim is reclaimable and required checks are never bypassed

### Requirement: A job kind with unproven prerequisites stays off the hosted path

A job kind whose prerequisites cannot be proven SHALL stay off the hosted path with the local operator node as its recorded basis.

#### Scenario: Prerequisites of a kind cannot be proven

- **WHEN** the prerequisites of a job kind cannot be proven
- **THEN** the kind stays off the hosted path
- **AND** the local operator node is its recorded basis

### Requirement: Hosted enablement grants no new orchestration or authority

The change that enables the hosted worker SHALL introduce no second orchestrator, queue or state store, SHALL NOT make an agent enter or read a credential, and SHALL give no local worker merge authority beyond the existing CI-only protocol.

#### Scenario: Hosted worker is enabled

- **WHEN** the hosted worker is enabled
- **THEN** no second orchestrator, queue or state store exists
- **AND** no agent enters or reads a credential
- **AND** no local worker gains merge authority beyond the existing CI-only protocol

### Requirement: The sandboxed writer profile confines writes to the writer's own areas

The platform-generated sandboxed writer profile SHALL allow writes only to the writer's disposable checkout, scratch home and writer temporary directory; SHALL deny writes to the integration checkout, its shared Git directory, every registered worktree, the operator Claude and config directories and the platform root.

#### Scenario: Writer attempts a write

- **WHEN** the sandboxed writer writes
- **THEN** writes are allowed only to the writer's disposable checkout, scratch home and writer temporary directory
- **AND** writes to the integration checkout, its shared Git directory, every registered worktree, the operator Claude and config directories and the platform root are denied

### Requirement: The sandboxed writer profile denies reads of operator credential stores

The platform-generated sandboxed writer profile SHALL deny reads of operator credential stores including SSH, GitHub CLI, Git credentials, keychains and the operator dev-platform configuration directory.

#### Scenario: Writer reads a credential store

- **WHEN** the sandboxed writer reads an operator credential store such as SSH, GitHub CLI, Git credentials, keychains or the operator dev-platform configuration directory
- **THEN** the read is denied

### Requirement: The sandboxed writer profile allows network access only to Anthropic hosts

The platform-generated sandboxed writer profile SHALL allow network access only to Anthropic hosts.

#### Scenario: Writer opens a network connection

- **WHEN** the sandboxed writer accesses the network
- **THEN** access is allowed only to Anthropic hosts

### Requirement: The sandboxed writer profile takes no weaker isolation settings

The platform-generated sandboxed writer profile SHALL NOT enable Apple Events or weaker network isolation and SHALL NOT take either setting from repository files.

#### Scenario: Repository requests Apple Events or weaker network isolation

- **WHEN** the profile is generated
- **THEN** Apple Events and weaker network isolation are not enabled
- **AND** neither setting is taken from repository files

### Requirement: An unproven sandboxed writer launch is refused without fallback

The sandboxed writer launch SHALL be refused explicitly on a platform where the sandboxed writer is not proven (anything other than macOS) or when the pinned sandbox runtime or the writer CLI is unavailable; the sandboxed writer launch SHALL NOT fall back to an unsandboxed launch.

#### Scenario: Unsupported platform or missing runtime

- **WHEN** the platform is anything other than macOS, or the pinned sandbox runtime or the writer CLI is unavailable
- **THEN** the sandboxed writer launch is refused explicitly
- **AND** no unsandboxed launch happens

### Requirement: A missing or exposed Claude writer token file fails the harness

The harness SHALL fail explicitly when the operator `[independent_review.login.claude] token_file` setting, file or value is missing or empty, or when the file is readable by group or others.

#### Scenario: Token file missing or too permissive

- **WHEN** the `[independent_review.login.claude] token_file` setting, file or value is missing or empty, or the file is readable by group or others
- **THEN** the harness fails explicitly

### Requirement: An ambient Claude OAuth token is removed

Any ambient `CLAUDE_CODE_OAUTH_TOKEN` SHALL be removed.

#### Scenario: Ambient token present

- **WHEN** an ambient `CLAUDE_CODE_OAUTH_TOKEN` is present
- **THEN** it is removed

### Requirement: The Claude writer token appears only in the writer process environment

The `CLAUDE_CODE_OAUTH_TOKEN` token of the sandboxed Claude writer SHALL be present only in the writer process environment, never in harness Git or push environments, command arguments, logs, posted results or routing evidence.

#### Scenario: Token placement

- **WHEN** the sandboxed Claude writer runs
- **THEN** the token is present only in the writer process environment
- **AND** it is absent from harness Git or push environments, command arguments, logs, posted results and routing evidence

### Requirement: The Claude writer token file is read-denied inside the sandbox

The token file location of the operator `[independent_review.login.claude] token_file` SHALL be read-denied inside the sandbox.

#### Scenario: Sandboxed process reads the token file

- **WHEN** a process inside the sandbox reads the token file location
- **THEN** the read is denied

### Requirement: A harness push without a gh credential fails explicitly

When `gh` reports no credential the deterministic harness push SHALL fail explicitly naming the missing `gh` credential, without echoing command output.

#### Scenario: gh reports no credential

- **WHEN** `gh` reports no credential for the deterministic harness push
- **THEN** the push fails explicitly naming the missing `gh` credential
- **AND** command output is not echoed

### Requirement: The harness push credential exists only in the push process

The active `gh` credential used by the deterministic harness push SHALL exist only in the environment of the single push process and SHALL NOT appear in argv, Git config files, writer checkouts or diagnostics.

#### Scenario: Push credential placement

- **WHEN** the deterministic harness push authenticates
- **THEN** the credential exists only in the environment of the single push process
- **AND** it does not appear in argv, Git config files, writer checkouts or diagnostics

### Requirement: Coordinator friction on an unmanaged branch has no Requirement

An unmanaged branch SHALL be recorded by the coordinator friction sink as having no Requirement.

#### Scenario: Friction on an unmanaged branch

- **WHEN** the coordinator friction sink records an event on an unmanaged branch
- **THEN** the event is recorded as having no Requirement

### Requirement: A malformed managed-looking branch fails coordinator friction recording

A branch that looks managed but whose identity is malformed SHALL fail friction recording explicitly, naming the branch.

#### Scenario: Malformed managed identity

- **WHEN** a branch looks managed but its identity is malformed
- **THEN** friction recording fails explicitly, naming the branch

### Requirement: Hosted and local coordinators attribute friction identically

The same coordinator friction attribution SHALL be produced by hosted and local coordinators.

#### Scenario: Hosted and local coordinators record friction

- **WHEN** a hosted coordinator and a local coordinator attribute the same event
- **THEN** they produce the same attribution

### Requirement: Head-bound gates do not survive a head move

Gates bound only to an older head SHALL NOT survive a head move.

#### Scenario: Head moves

- **WHEN** the head of a candidate moves
- **THEN** gates bound only to the older head are no longer valid

### Requirement: Lost content-bound gates are restored only after proving trusted pushes

A coordinator command SHALL restore content-bound gates already lost on a candidate in `finalize-pending`, `review-pending` or `blocked-retryable` only after proving every head move from a record holding those gates to the current head was a trusted harness push with the same task-content digest; any other history SHALL be refused, naming the failing step.

#### Scenario: History of trusted pushes is proven

- **GIVEN** a candidate in `finalize-pending`, `review-pending` or `blocked-retryable` that lost content-bound gates
- **WHEN** every head move from a record holding those gates to the current head is proven to be a trusted harness push with the same task-content digest
- **THEN** the coordinator command restores those gates

#### Scenario: Other history

- **WHEN** any head move cannot be proven that way
- **THEN** restoration is refused, naming the failing step

### Requirement: Gate restoration performs no review, claim, rewrite or bypass

Restoration of lost content-bound gates SHALL NOT run a review, register a claim, rewrite branch history or bypass a gate.

#### Scenario: Gates are restored

- **WHEN** the coordinator command restores content-bound gates
- **THEN** no review runs and no claim is registered
- **AND** branch history is not rewritten and no gate is bypassed

### Requirement: An unobservable pilot value is recorded as unobserved

In the hosted pilot placement record, a value that cannot be observed SHALL be recorded as unobserved with the reason and SHALL NOT be estimated as measured.

#### Scenario: Pilot value cannot be observed

- **WHEN** a value of the pilot placement record cannot be observed
- **THEN** it is recorded as unobserved with the reason
- **AND** it is not estimated as measured

### Requirement: A pilot job kind with unproven prerequisites stays local with a named basis

A hosted lifecycle job kind whose prerequisites cannot be proven SHALL stay off the hosted path and the pilot placement record SHALL name the basis for the local operator node.

#### Scenario: Kind prerequisites unproven in the pilot

- **WHEN** the prerequisites of a hosted lifecycle job kind cannot be proven
- **THEN** the kind stays off the hosted path
- **AND** the pilot placement record names the basis for the local operator node

### Requirement: The hosted pilot adds no orchestration or merge authority

The hosted pilot SHALL introduce no second orchestrator, queue or state store and SHALL give no local worker merge authority.

#### Scenario: Pilot runs

- **WHEN** the hosted pilot runs
- **THEN** no second orchestrator, queue or state store exists
- **AND** no local worker gains merge authority

### Requirement: The worker read cache never changes job selection

The disposable read cache SHALL never change which jobs a worker offers or claims: job selection, claim expiry and attempt counters SHALL equal those of a cache-free read at the same GitHub state.

#### Scenario: Cached and cache-free reads

- **WHEN** a worker reads through the disposable read cache at a given GitHub state
- **THEN** its job selection, claim expiry and attempt counters equal those of a cache-free read at the same GitHub state

### Requirement: A corrupt worker read cache fails the run explicitly

A corrupt or inconsistent disposable read cache SHALL fail the worker run explicitly naming the cache file and its reset, and SHALL NOT be bypassed silently.

#### Scenario: Cache is corrupt

- **WHEN** the disposable read cache is corrupt or inconsistent
- **THEN** the worker run fails explicitly naming the cache file and its reset
- **AND** the cache is not bypassed silently

### Requirement: Worker writes bypass the read cache

Claim, result and every other write SHALL bypass the disposable read cache.

#### Scenario: Worker writes

- **WHEN** a worker writes a claim, a result or any other write
- **THEN** the write bypasses the disposable read cache

### Requirement: A scheduled post-merge round repeats work-next until idle or bounded

One scheduled round of the operator-Mac runner SHALL repeat `work-next` until `work-next` reports idle or a bound is reached: a maximum number of runs, a maximum duration, the first failed run, or a GitHub REST remainder below a required threshold.

#### Scenario: Round reaches idle or a bound

- **WHEN** a scheduled round runs
- **THEN** it repeats `work-next` until `work-next` reports idle or a bound is reached
- **AND** the bounds are a maximum number of runs, a maximum duration, the first failed run, or a GitHub REST remainder below a required threshold

### Requirement: The scheduled round reads the REST remainder without spending the limit

The GitHub REST remainder SHALL be read without spending the counted limit before the scheduled round and between runs.

#### Scenario: Remainder is read

- **WHEN** the scheduled round starts or moves to its next run
- **THEN** the GitHub REST remainder is read without spending the counted limit

### Requirement: A post-merge PR is attempted at most once per scheduled round

Within one scheduled round of the operator-Mac runner, a PR whose post-merge run ended `blocked` or `failed` SHALL be excluded from every further `work-next` run of that scheduled round, so an obligation is attempted at most once per round while other PRs are still served.

#### Scenario: Run ends blocked or failed

- **WHEN** a PR's post-merge run ends `blocked` or `failed` within a scheduled round
- **THEN** the PR is excluded from every further `work-next` run of that round
- **AND** other PRs are still served

### Requirement: The scheduled round verifies the cleanup process-check tool before claiming

Before claiming any job a scheduled round of the operator-Mac runner SHALL verify that the process-check tool the cleanup job needs resolves on the runner's PATH, and SHALL fail explicitly naming the process-check tool otherwise.

#### Scenario: Process-check tool is missing

- **WHEN** the process-check tool the cleanup job needs does not resolve on the runner's PATH
- **THEN** the round fails explicitly naming the tool before claiming any job

### Requirement: Scheduled rounds and runs are journaled

Every scheduled round of the operator-Mac runner and every `work-next` run SHALL be recorded in an append-only run journal with its outcome.

#### Scenario: Round completes

- **WHEN** a scheduled round and its `work-next` runs complete
- **THEN** each is recorded with its outcome in the append-only run journal

### Requirement: Invalid scheduled round inputs fail the round explicitly

Missing or invalid configuration, credentials, an unreadable rate limit or an unwritable run journal SHALL fail the scheduled round explicitly.

#### Scenario: Round input invalid

- **WHEN** configuration or credentials are missing or invalid, the rate limit is unreadable or the run journal is unwritable
- **THEN** the scheduled round fails explicitly

### Requirement: The scheduled runner opens no attention path of its own

The scheduled operator-Mac runner SHALL NOT open its own attention path: a spent post-merge obligation stays reported by the existing attention on the merged PR and in the lifecycle overview.

#### Scenario: Obligation is spent

- **WHEN** a post-merge obligation is spent
- **THEN** the runner opens no attention path of its own
- **AND** the obligation stays reported by the existing attention on the merged PR and in the lifecycle overview

### Requirement: An environment defect releases the post-merge claim and fails work-next

When a claimed post-merge job cannot run because the executing environment is defective — the cleanup's active-process check is unavailable — the executor SHALL release its claim and `work-next` SHALL exit non-zero naming the defect, so the attempt counter of the obligation is unchanged and the caller fails visibly.

#### Scenario: Active-process check unavailable

- **WHEN** the cleanup's active-process check is unavailable for a claimed post-merge job
- **THEN** the executor releases its claim and `work-next` exits non-zero naming the defect
- **AND** the attempt counter of the obligation is unchanged and the caller fails visibly

### Requirement: A refusal inherent to the post-merge obligation stays blocked

A refusal that is a property of the post-merge obligation (an active board claim, a dirty or mismatched worktree, local commits outside the merged PR) SHALL remain a `blocked` outcome.

#### Scenario: Obligation-level refusal

- **WHEN** a post-merge job is refused because of an active board claim, a dirty or mismatched worktree, or local commits outside the merged PR
- **THEN** the outcome is `blocked`

### Requirement: A cleanup without a task-branch worktree completes as already-clean

A cleanup that finds no worktree of the task branch SHALL complete the obligation with the outcome `already-clean`.

#### Scenario: No worktree of the task branch

- **WHEN** a cleanup finds no worktree of the task branch
- **THEN** it completes the obligation with the outcome `already-clean`

### Requirement: A positive post-merge re-offer sequence gives a fresh attempt budget

With an operator post-merge re-offer sequence greater than zero, an obligation SHALL count as complete when any trusted outcome of any attempt under any earlier or current sequence completed it; an incomplete obligation SHALL be offered under job ids of the current sequence with attempts `0..MAX_POST_MERGE_ATTEMPTS-1`, giving a fresh attempt budget.

#### Scenario: Obligation completed under an earlier sequence

- **GIVEN** a re-offer sequence greater than zero
- **WHEN** a trusted outcome of an attempt under an earlier or the current sequence completed an obligation
- **THEN** the obligation counts as complete

#### Scenario: Incomplete obligation after a re-offer

- **GIVEN** a re-offer sequence greater than zero
- **WHEN** an obligation is incomplete
- **THEN** it is offered under job ids of the current sequence with attempts `0..MAX_POST_MERGE_ATTEMPTS-1`

### Requirement: A post-merge re-offer sequence without its event is malformed

A coordinator record whose post-merge re-offer sequence has no matching re-offer event SHALL be rejected as malformed.

#### Scenario: Sequence without event

- **WHEN** a record carries a re-offer sequence with no matching re-offer event
- **THEN** the record is rejected as malformed

### Requirement: Exhaustion under the current re-offer sequence is reported unchanged

Exhaustion of a post-merge obligation under the current re-offer sequence SHALL be reported as before.

#### Scenario: Obligation exhausted again

- **WHEN** a post-merge obligation is exhausted under the current re-offer sequence
- **THEN** the exhaustion is reported as before

### Requirement: A merged PR with a post-merge obligation is found at any position

A merged PR with an open or exhausted post-merge obligation SHALL be found whatever its position among closed PRs, and the lifecycle overview SHALL consider the same set of merged candidates.

#### Scenario: Old merged PR with an open obligation

- **WHEN** a merged PR with an open or exhausted post-merge obligation is outside the bounded page of recently updated closed PRs
- **THEN** it is found
- **AND** the lifecycle overview considers the same set of merged candidates

### Requirement: An unreadable merged-candidate source fails instead of truncating

If any part of the merged candidate source cannot be read, the command SHALL fail naming the failed read and SHALL NOT present a truncated set as complete.

#### Scenario: Candidate source read fails

- **WHEN** a part of the merged candidate source cannot be read
- **THEN** the command fails naming the failed read
- **AND** no truncated set is presented as complete

### Requirement: work-next labels a merged candidate settled only when nothing remains

`work-next` SHALL label a merged candidate `post-merge:settled` only when derivation shows no next post-merge job and no exhausted obligation, SHALL NOT write the label in `--dry-run`, and SHALL fail the run when the label write fails.

#### Scenario: Nothing remains for a merged candidate

- **WHEN** derivation shows no next post-merge job and no exhausted obligation for a merged candidate
- **THEN** `work-next` labels it `post-merge:settled`, except in `--dry-run`
- **AND** a failed label write fails the run

### Requirement: work-next with a PR reads that PR directly

`work-next --pr N` SHALL read PR N directly rather than selecting it from the listing, so `work-next --pr N` applies to any merged PR with a lifecycle record.

#### Scenario: Targeted merged PR

- **WHEN** `work-next --pr N` runs for a merged PR with a lifecycle record
- **THEN** PR N is read directly rather than selected from the listing

### Requirement: The release reaching the limit posts post-merge attention

The worker run whose release reaches the `MAX_RELEASES` limit SHALL post the existing post-merge attention on the merged PR, SHALL fail visibly when that post fails, and SHALL NOT publish `blocked-escalation` for the merged PR.

#### Scenario: Release reaches the limit

- **WHEN** a worker run's release of a post-merge job reaches the `MAX_RELEASES` limit
- **THEN** the run posts the existing post-merge attention on the merged PR
- **AND** it fails visibly when that post fails
- **AND** it publishes no `blocked-escalation` for the merged PR

### Requirement: A release-exhausted post-merge obligation is reported and re-offerable

A post-merge obligation exhausted by reaching the `MAX_RELEASES` release limit SHALL be reported by the lifecycle overview and accepted by `reoffer-post-merge`, whose fresh job ids start a fresh release budget.

#### Scenario: Exhausted obligation is re-offered

- **WHEN** a post-merge obligation is exhausted by releases
- **THEN** the lifecycle overview reports it
- **AND** `reoffer-post-merge` accepts it and its fresh job ids start a fresh release budget

### Requirement: Pre-merge release escalation is unchanged

The release escalation of pre-merge jobs SHALL be unchanged.

#### Scenario: Pre-merge job reaches the release limit

- **WHEN** a pre-merge job is released to its limit
- **THEN** its release escalation is unchanged
