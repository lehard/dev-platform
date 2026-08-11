## MODIFIED Requirements

### Requirement: Rollout fails closed on project ambiguity or conflicts

Automatic rollout SHALL leave the downstream default branch untouched when Copier metadata is missing or unexpected, a downgrade is requested, an unresolved Copier/Git conflict remains, project validation fails, or an unexpected rollout branch collision exists. Detection of an already-pending rollout PR SHALL be performed by a testable, platform-owned helper that filters structured GitHub API JSON by the exact reserved branch, configured base branch, and expected rollout automation identity -- not by ad hoc shell/`jq` argument combinations, human-readable `gh` command output parsing, or PR title/body text matching.

#### Scenario: Copier produces a rejected patch

- **WHEN** an exact-version update leaves any non-ignored `*.rej` file
- **THEN** the rollout job fails and does not push or merge changes to the downstream default branch

#### Scenario: An update PR for the same target already exists

- **WHEN** rollout finds the deterministic target branch already associated with an open pull request
- **THEN** it reports the rollout as already pending without force-pushing or opening a duplicate PR
- **AND** that determination is made by the structured pending-PR helper, reusing the same eligibility rules (exact branch, base, and automation identity) already used for rollout PR supersession

#### Scenario: Pending-PR detection uses only supported CLI/API surface

- **WHEN** the rollout job checks for an already-pending PR
- **THEN** it SHALL NOT pass unsupported flags to the `gh` CLI
- **AND** a regression test SHALL assert the workflow does not combine `--jq` with a separate `--arg` flag on any `gh` invocation

### Requirement: Repeated managed rollout failures against the same project are surfaced to a human

The platform SHALL maintain a durable, cross-run record of consecutive terminal `blocked` managed-rollout attempts per project, independent of any single ephemeral workflow run. When that count reaches a fixed threshold, the platform SHALL escalate beyond the existing per-attempt annotation into a distinct, labeled, human-discoverable alert. The record SHALL reset the next time that project's rollout preparation succeeds. Before either the tracking label or the alert label is referenced, the platform SHALL idempotently ensure both exist on the tracker repository, using only the least-privilege permission already granted to the rollout job.

This tracking layer SHALL be strictly additive: a failure inside it, including a failure to bootstrap its own labels, SHALL NOT change rollout's own pass/fail result for the current attempt, SHALL NOT retry, push, merge, or affect PR-creation, and SHALL NOT modify any existing safety guard, recovery eligibility, or credential scope.

#### Scenario: First failure against a project opens a tracking record
- **GIVEN** a project has no open rollout-failure tracking record
- **WHEN** its managed rollout preparation reaches a terminal blocked state
- **THEN** a new durable tracking record is created for that exact project
- **AND** its consecutive-failure count is `1`
- **AND** no alert-threshold escalation occurs yet

#### Scenario: Tracking label does not yet exist on the tracker repository

- **GIVEN** the tracker repository does not yet have the `rollout-failure-streak` or `rollout-alert` label
- **WHEN** the tracking layer needs to create or label a tracking issue
- **THEN** the missing label is created automatically before it is referenced
- **AND** no manual repository UI setup is required

#### Scenario: Label bootstrap is idempotent

- **WHEN** label bootstrap runs against a tracker repository that already has the label
- **THEN** it succeeds without error and does not create a duplicate label

#### Scenario: Repeated failures increment the same tracking record
- **GIVEN** a project already has an open rollout-failure tracking record with a readable prior state
- **WHEN** its managed rollout preparation reaches another terminal blocked state
- **THEN** the existing record's consecutive-failure count increments by exactly one
- **AND** the record retains which release first failed and is updated with the most recent failure's category and reason
- **AND** no second tracking record is created for the same project

#### Scenario: Consecutive failures cross the alert threshold
- **GIVEN** a project's tracking record reaches a consecutive-failure count of 3
- **WHEN** the platform updates that record
- **THEN** the record is labeled as an outstanding alert
- **AND** a distinct workflow warning annotation identifies the project, the streak length, and the tracking record
- **AND** the underlying rollout attempt remains in its original failed state

#### Scenario: A successful rollout resets the streak
- **GIVEN** a project has an open rollout-failure tracking record
- **WHEN** that project's managed rollout preparation next succeeds
- **THEN** the tracking record is closed with a note of how many consecutive failures preceded the resolution and at which release it resolved
- **AND** the record is not deleted, remaining as a historical entry
- **AND** a subsequent new failure against that project opens a fresh record starting at a consecutive-failure count of `1`

#### Scenario: A successful rollout with no prior open record is a no-op
- **GIVEN** a project has no open rollout-failure tracking record
- **WHEN** that project's managed rollout preparation succeeds
- **THEN** the platform makes no tracking-record change

#### Scenario: Prior tracking state cannot be read
- **GIVEN** a project has an open rollout-failure tracking record whose state cannot be parsed
- **WHEN** another terminal blocked attempt occurs against that project
- **THEN** the platform treats the streak as already at or above the alert threshold rather than resetting it to a lower count
- **AND** escalates as in the threshold-crossing scenario
- **AND** does not silently discard the unreadable prior record

#### Scenario: The tracking layer itself fails
- **GIVEN** a rollout attempt has already reached a terminal status
- **WHEN** creating, reading, or updating the durable tracking record fails for any reason, including label bootstrap
- **THEN** that failure is surfaced as a visible warning in the run's own output
- **AND** it SHALL NOT change the rollout attempt's already-determined success or failure result
- **AND** it SHALL NOT retry, push, merge, or otherwise act beyond the tracking record itself

## ADDED Requirements

### Requirement: Platform-owned rollout helpers are invoked from their actual checkout path

Every platform-owned Python helper invoked from a workflow job that checks out platform tooling into a non-root path (for example `platform/` alongside a separate downstream `target/` checkout) SHALL be invoked using that actual path. A regression test SHALL verify, for each such job, that every reference to a known platform-owned root-level script resolves under the job's real checkout layout rather than relying solely on a passing workflow run.

#### Scenario: Rollout job checks out platform tooling into a non-root path

- **GIVEN** the `rollout` job in `.github/workflows/rollout.yml` checks out immutable platform tooling into `platform/` and the downstream project into `target/`
- **WHEN** any step in that job invokes a platform-owned root-level script
- **THEN** the invocation SHALL use the `platform/`-prefixed path
- **AND** a regression test SHALL fail if a bare unprefixed path is introduced

#### Scenario: A different workflow uses a single root checkout

- **GIVEN** a workflow job checks out the platform repository directly at the job's working directory with no separate `platform/` path
- **WHEN** that job invokes a platform-owned root-level script
- **THEN** the bare root-relative path is correct for that job's layout
- **AND** the path-correctness regression test SHALL evaluate each job against its own actual checkout layout, not a single assumed layout
