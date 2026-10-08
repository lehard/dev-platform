## ADDED Requirements

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

A repair or integration-repair job SHALL name exactly one provider. That provider SHALL be the provider of the originating task route recorded on the candidate handoff, unless an explicit recorded operator re-offer (a switch-provider event in the job record) names the job's provider, which then authorizes it; any other provider SHALL fail explicitly. A worker SHALL declare the provider of its executor, SHALL be offered and SHALL claim such a job only when the declared provider equals the recorded one, and SHALL record that provider in its claim and result. A job with a missing, empty, unknown or self-contradictory provider SHALL fail explicitly naming the pull request. An unauthorized worker SHALL leave the job claimable by a matching worker and report why it claimed nothing.

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
