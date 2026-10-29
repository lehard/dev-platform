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

### Requirement: A sandboxed writer launch uses a platform-generated OS sandbox profile

The lifecycle harness SHALL provide a sandboxed writer launch that runs the LLM command under sandbox-runtime with a profile generated by platform code. The profile SHALL allow writes only to the writer's disposable checkout, scratch home and writer temporary directory; SHALL deny writes to the integration checkout, its shared Git directory, every registered worktree, the operator Claude and config directories and the platform root; SHALL deny reads of operator credential stores including SSH, GitHub CLI, Git credentials, keychains and the operator dev-platform configuration directory; and SHALL allow network access only to Anthropic hosts. The profile SHALL NOT enable Apple Events or weaker network isolation and SHALL NOT take either setting from repository files. The launch SHALL be refused explicitly on a platform where the sandboxed writer is not proven (anything other than macOS) or when the pinned sandbox runtime or the writer CLI is unavailable; it SHALL NOT fall back to an unsandboxed launch.

#### Scenario: Profile protects the integration checkout
- **GIVEN** an integration repository with a linked task worktree and a disposable writer checkout
- **WHEN** the harness generates the sandbox profile
- **THEN** only the disposable checkout, scratch home and writer tmp are writable
- **AND** the integration checkout, its common Git directory and every registered worktree are write-denied

#### Scenario: Unsupported platform
- **WHEN** a sandboxed writer launch is requested on a non-macOS platform
- **THEN** the launch fails before any process starts with an error naming the unproven platform

### Requirement: The Claude writer credential is scoped to the writer process

A sandboxed Claude writer SHALL receive `CLAUDE_CODE_OAUTH_TOKEN` only from the operator `[independent_review.login.claude] token_file`. The harness SHALL fail explicitly when that setting, file or value is missing or empty, or when the file is readable by group or others. Any ambient `CLAUDE_CODE_OAUTH_TOKEN` SHALL be removed. The token SHALL be present only in the writer process environment, never in harness Git or push environments, command arguments, logs, posted results or routing evidence. The token file location SHALL be read-denied inside the sandbox.

#### Scenario: Token stays out of the harness
- **WHEN** a sandboxed Claude writer is launched and its result is validated and pushed
- **THEN** the writer environment carries the token from the token file
- **AND** the harness Git and push environments and every recorded argument do not contain it

#### Scenario: Token file too open
- **WHEN** the token file mode grants group or other access
- **THEN** the launch is refused with an error naming the file and required mode

### Requirement: The sandboxed launch accounts for runtime path and argument constraints

The sandboxed launch SHALL start the sandbox runtime with a short temporary directory for its own socket and SHALL pass the harness writer temporary directory as `CLAUDE_CODE_TMPDIR` in the sandbox runtime's own environment, which the runtime uses as the writer's temporary directory (assignments inside the sandboxed command are not honored for these variables); and SHALL pass the writer argv as one `bash -c` script built with shell quoting so a multi-word task stays one argument.

#### Scenario: Claude writer shell tool has a writable temporary directory
- **WHEN** a sandboxed Claude writer runs a shell command
- **THEN** its temporary directory is the harness writer temporary directory and the shell tool starts

#### Scenario: Multi-word task survives the runtime
- **WHEN** the final writer argument is a multi-word task
- **THEN** the writer receives it as exactly one argument

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

### Requirement: Coordinator friction is attributed by public work identity

The coordinator friction sink SHALL attribute an event to the Requirement through the public work identity encoded in the managed candidate branch (`BR-N` for the Requirement, `BR-N/TM` for a child), derived without reading runner configuration, the Development Backlog or any other source. An unmanaged branch SHALL be recorded as having no Requirement; a branch that looks managed but whose identity is malformed SHALL fail friction recording explicitly, naming the branch. The same attribution SHALL be produced by hosted and local coordinators.

#### Scenario: Hosted review with material findings records friction
- **GIVEN** a managed candidate and a hosted contract without Development Backlog configuration
- **WHEN** a hosted review finds material findings
- **THEN** one run records `repair-pending` and a trusted coordinator evidence record bound to the Requirement's work identity
- **AND** no further review round or evidence commit is created

#### Scenario: Malformed managed branch
- **WHEN** friction must be recorded for a candidate whose branch looks managed but carries a malformed identity
- **THEN** recording fails with an error naming the branch
- **AND** no transition is published without durable friction

### Requirement: A review job proves friction can be attributed before it reviews

A review or repair job SHALL derive the friction attribution of its candidate after its claim is validated and before the reviewer or writer starts and before any evidence push. When it cannot, the job SHALL fail explicitly with the named cause and SHALL NOT move the candidate head.

#### Scenario: Attribution unavailable
- **WHEN** a hosted review job claims a candidate whose friction attribution cannot be derived
- **THEN** the run fails before the reviewer starts, naming the cause
- **AND** the candidate head and records are unchanged

### Requirement: A worker's own push is not mistaken for a foreign head change

After a successful lease-protected push of its validated result, a worker SHALL wait a bounded time for the pull request head to report the pushed head before deciding the job's outcome. A head that becomes any other commit, or a claim that changes, SHALL still discard the job. A head that does not converge within the bound SHALL fail the job explicitly with the cause instead of discarding it silently.

#### Scenario: Pull request head lags behind the push
- **WHEN** the pull request API still reports the job head immediately after the worker's own successful push and then reports the pushed head
- **THEN** the job publishes its transition for the pushed head and is not discarded

#### Scenario: Someone else moves the head
- **WHEN** the pull request head becomes a commit other than the job head or the pushed head, or the claim changes
- **THEN** the job is discarded and nothing is published for it

### Requirement: Content-bound gates survive trusted harness pushes

Gates bound to task-content identity SHALL remain valid on a head reached through a trusted harness push of the same candidate when the task-content digest is unchanged, including when an interrupted job is recovered from its validated-push receipt and when the next job claims that head. Gates bound only to an older head SHALL NOT survive a head move. A coordinator command SHALL restore content-bound gates already lost on a candidate in `finalize-pending`, `review-pending` or `blocked-retryable` only after proving every head move from a record holding those gates to the current head was a trusted harness push with the same task-content digest; any other history SHALL be refused, naming the failing step. Restoration SHALL NOT run a review, register a claim, rewrite branch history or bypass a gate.

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

A bounded pilot on real pull requests of the platform repository SHALL end in a durable record of, for each hosted lifecycle job kind, whether it runs hosted or remains on the local fallback, with the verified constraints behind the decision: provider runtime and credential availability, credential-boundary proof, token scope, observed duration, cost and limits, and failure behavior. A value that cannot be observed SHALL be recorded as unobserved with the reason and SHALL NOT be estimated as measured. A kind whose prerequisites cannot be proven SHALL stay off the hosted path and the record SHALL name the basis for the local operator node. The pilot SHALL introduce no second orchestrator, queue or state store and SHALL give no local worker merge authority.

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

### Requirement: Post-merge lifecycle work runs on the operator Mac on a schedule

The platform SHALL provide a scheduled operator-Mac runner that executes the existing retrospective, terminal-reconciliation and cleanup jobs through `lifecycle_workers.py work-next --run` and its claim/result protocol, with no queue, claim format or state store of its own. One scheduled round SHALL repeat `work-next` until it reports idle or a bound is reached: a maximum number of runs, a maximum duration, the first failed run, or a GitHub REST remainder below a required threshold. The remainder SHALL be read without spending the counted limit before the round and between runs. Every round and every `work-next` run SHALL be recorded in an append-only run journal with its outcome. Missing or invalid configuration, credentials, an unreadable rate limit or an unwritable journal SHALL fail the round explicitly. The runner SHALL NOT open its own attention path: a spent post-merge obligation stays reported by the existing attention on the merged PR and in the lifecycle overview.

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

#### Scenario: Missing configuration
- **WHEN** a required argument, the `gh` credential or the journal directory is missing or invalid
- **THEN** the runner exits non-zero naming it and runs nothing

### Requirement: The post-merge runner LaunchAgent is rendered by the platform and installed by the owner

The platform SHALL render the LaunchAgent definition for the runner with explicit absolute paths and a start interval between 10 and 15 minutes, SHALL install or remove it only on an explicit command, and SHALL NOT install it as a side effect of tests, validation or release.

#### Scenario: Render without installing
- **WHEN** the owner asks to print the LaunchAgent
- **THEN** the plist is printed and nothing is written or loaded

#### Scenario: Unload fails on removal
- **WHEN** a live agent cannot be unloaded
- **THEN** the plist is kept and the command fails naming the launchctl error
