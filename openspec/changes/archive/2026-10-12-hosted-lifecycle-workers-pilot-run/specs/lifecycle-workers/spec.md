## ADDED Requirements

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
