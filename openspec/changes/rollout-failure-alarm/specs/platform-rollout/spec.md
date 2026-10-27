## MODIFIED Requirements

### Requirement: Repeated managed rollout failures against the same project are surfaced to a human

The platform SHALL maintain a durable, cross-run record of consecutive terminal `blocked` managed-rollout attempts per project, independent of any single ephemeral workflow run. When that count reaches a fixed threshold, the platform SHALL escalate beyond the existing per-attempt annotation into a distinct, labeled, human-discoverable alert. The record SHALL reset the next time that project's rollout preparation succeeds. Before either the tracking label or the alert label is referenced, the platform SHALL idempotently ensure both exist on the tracker repository, using only the least-privilege permission already granted to the rollout job.

This tracking layer SHALL NOT retry, push, merge, or affect PR-creation, and SHALL NOT modify any existing safety guard, recovery eligibility, or credential scope. A failure inside it, including a failure to bootstrap its own labels or a missing required input, SHALL fail the tracking step explicitly with a message naming what failed; it SHALL NOT be converted into a warning. The failure record is written exactly when rollout preparation itself failed; failures before preparation are covered by the release-level rollout alarm.

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
- **WHEN** creating, reading, or updating the durable tracking record fails for any reason, including label bootstrap or a missing required token
- **THEN** the tracking step fails with a non-zero exit and a message naming the failed operation
- **AND** the failure is not downgraded to a warning or hidden by `continue-on-error`
- **AND** it SHALL NOT retry, push, merge, or otherwise act beyond the tracking record itself

#### Scenario: Preparation diagnostic is missing when recording a failure
- **GIVEN** rollout preparation failed for a project
- **WHEN** the failure record is written and the preparation diagnostic file is missing or unreadable
- **THEN** the tracking step fails naming the missing diagnostic
- **AND** no `unknown` category or reason is substituted

## ADDED Requirements

### Requirement: Failed managed rollout runs raise a release-level alarm

Every `Roll Out Platform` run, whether dispatched by the release workflow or manually for all managed projects or one repository, SHALL end with an always-running alarm job that runs reviewed workflow-ref code and inspects the current run attempt's own jobs. When the plan job or any per-project job did not succeed (failed, cancelled, timed out or never finished), the platform SHALL open one durable alert per release tag in the platform repository, or add to the open one, naming the release tag, each failed stage or target repository, its failed step and its error text, together with the run link and dispatch context. A fully successful run SHALL raise no alarm. The alarm SHALL NOT retry, repair, push or merge anything. When the alarm cannot be delivered, the alarm job SHALL fail with a message naming what failed.

#### Scenario: Plan stage fails
- **GIVEN** a rollout run whose plan job fails, for example because the operator registry checkout reports the repository not found
- **WHEN** the alarm job runs
- **THEN** an open alert labeled `rollout-alert` for the requested release tag names stage `plan`, its failed step and the error text
- **AND** the release tag is named even when plan failed before resolving it, using the same rule as plan (`version` input or `v<VERSION>`)

#### Scenario: One target fails while others succeed
- **GIVEN** a rollout run in which some per-project jobs succeed and one fails or is cancelled
- **WHEN** the alarm job runs
- **THEN** the alert names only the failed target repositories with their failed step and error
- **AND** the run is reported as a failure, not as success

#### Scenario: Release-dispatched and manually dispatched runs are both covered
- **WHEN** a rollout run started by the release workflow, or a manual dispatch for all projects or for one `repository`, has a failed job
- **THEN** the alert is raised and records the event, the triggering actor and the requested scope

#### Scenario: A later failing run for the same release
- **GIVEN** an alert for release `vX.Y.Z` is already open
- **WHEN** another rollout run for `vX.Y.Z` fails
- **THEN** the failure is added to the same alert and no second alert is opened for that tag

#### Scenario: Successful run
- **WHEN** every job of a rollout run succeeds
- **THEN** no alert is created
- **AND** if an alert for that release is open, it receives a note that this run succeeded for its scope and stays open

#### Scenario: Failed job without an error annotation
- **WHEN** a failed job has no failure-level annotation
- **THEN** the alert states that no error annotation was recorded and links the job log
- **AND** no error text is invented

#### Scenario: The alarm cannot be delivered
- **WHEN** reading the run's jobs, bootstrapping the label, or creating or commenting on the alert fails
- **THEN** the alarm job exits non-zero naming the failed operation
- **AND** it is not hidden by `continue-on-error`
