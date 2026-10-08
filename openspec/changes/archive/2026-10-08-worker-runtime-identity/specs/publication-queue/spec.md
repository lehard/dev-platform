## ADDED Requirements

### Requirement: Handoff records the originating task route

The developer handoff that admits a candidate SHALL record the originating task's executor route (provider, profile and change) in the authenticated handoff record, resolved from the task's durable routing evidence in the developer checkout. Later lifecycle jobs for the candidate SHALL take their provider from that record rather than from the coordinator checkout, and a missing, unreadable, mismatched or unsupported route SHALL fail explicitly instead of publishing a job for a default or unresolved provider.

#### Scenario: Coordinator publishes repair from another checkout

- **WHEN** a required-check or integration failure makes the coordinator publish a repair job from a checkout whose own task route differs
- **THEN** the job names the provider recorded on the candidate's handoff

#### Scenario: Route cannot be resolved at handoff

- **WHEN** the developer checkout has no valid routing evidence for the task's change
- **THEN** admission fails with an error naming the change and writes no admission comment

#### Scenario: Candidate has no recorded route

- **WHEN** a repair or integration-repair job is to be published for a candidate whose record carries no route, or whose recorded change differs from its task identity
- **THEN** publication fails explicitly asking for a new developer handoff and no job is published

#### Scenario: Route is stable across head changes

- **WHEN** the candidate head advances within the same task
- **THEN** the recorded route is inherited by the new exact-head record
