## ADDED Requirements

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
