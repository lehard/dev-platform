## ADDED Requirements

### Requirement: Post-merge jobs are offered fresh first

When every requested kind is a post-merge kind, `work-next` SHALL offer open PRs first, then merged PRs by merge time, newest first. It SHALL derive candidates in that order and stop at the first claimable job, reading a PR known only from the `lifecycle:merged` listing when reached. A run with no job SHALL derive every candidate. Order of other kinds is unchanged.

#### Scenario: Fresh PR before the historical tail
- **GIVEN** dozens of old merged PRs with open post-merge jobs and a newly merged PR with an open job
- **WHEN** `work-next` with post-merge kinds runs
- **THEN** it offers the new PR's job without reading the older PRs

#### Scenario: Nothing to claim
- **WHEN** no candidate has a claimable post-merge job
- **THEN** every candidate is derived, settled chains are labeled and the run reports idle

### Requirement: Settled merged PRs are not re-read

Post-merge discovery and the lifecycle overview SHALL skip a closed PR labeled `post-merge:settled`, including one in the recent closed page. The GitHub read cache SHALL parse its file at most once per process while the file is unchanged, still revalidate every read with GitHub, and fail explicitly when the file is corrupt.

#### Scenario: Settled PR in the recent page
- **WHEN** a recently closed PR carries `post-merge:settled`
- **THEN** discovery does not read its comments

#### Scenario: Cache changed by another process
- **WHEN** the cache file changes between two reads of one process
- **THEN** the second read reloads and validates the file

### Requirement: The runner's round budget bounds starts, not runs

The post-merge runner SHALL start no `work-next` run after the round deadline and SHALL bound a started run only by the claim TTL. Reaching the deadline SHALL end the round with outcome `max-seconds`, not `failed`. A run killed at the claim TTL SHALL fail the round.

#### Scenario: Deadline reached during a run
- **WHEN** the round deadline passes while a run executes
- **THEN** the run completes and is journaled, and the round ends `max-seconds`

#### Scenario: Run exceeds the claim TTL
- **WHEN** a run exceeds the claim TTL
- **THEN** it is killed and the round ends `failed` naming the timeout

### Requirement: Composition post-merge checkouts use the trusted contract

A composition post-merge job that checks out an exact historical head SHALL install the integration checkout's platform contract into it, not the head's own public contract. A missing trusted contract SHALL fail the job naming the file; no key is defaulted.

#### Scenario: Head predates a required key
- **WHEN** a composition terminal job checks out a head whose public contract lacks `agent_tools`
- **THEN** the gate check reads the installed integration contract and does not fail on `agent_tools`
