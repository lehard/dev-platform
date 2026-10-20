## MODIFIED Requirements

### Requirement: Coordinator friction evidence is durable on the candidate pull request

Meaningful lifecycle and friction events recorded by the coordinator SHALL be persisted as a trusted, versioned evidence comment on the candidate pull request through the existing authenticated lifecycle comment channel, before the transition that produced them is published. Each record SHALL bind the Requirement through its public work identity derived from the managed candidate branch (or prove none for an unmanaged branch), SHALL NOT contain a private Development Backlog reference, and SHALL bind the pull request number, exact head, lifecycle stage and the worker run identity, SHALL be idempotent per dedupe key, and SHALL be authenticated by the same trust rules as other lifecycle markers. A persistence failure SHALL fail the transition and the run visibly; the coordinator SHALL NOT proceed with machine-local-only evidence.

#### Scenario: Ephemeral runner ends

- **WHEN** a coordinator run on an ephemeral runner records friction for a candidate and the runner is discarded
- **THEN** a trusted evidence record bound to the Requirement's work identity, head, stage and worker remains on the pull request
- **AND** the Requirement retrospective lists it for that Requirement

#### Scenario: Retried transition

- **WHEN** an interrupted or scheduled run repeats the same transition for the same head and attempts
- **THEN** no second evidence record is posted

#### Scenario: Forged or malformed record

- **WHEN** an evidence comment is authored by an untrusted account
- **THEN** it is ignored
- **WHEN** a trusted evidence record is malformed or contradicts its pull request or head
- **THEN** reading it raises a named error and is not skipped

#### Scenario: Persistence fails

- **WHEN** the evidence comment cannot be posted or the Requirement work identity cannot be derived from a managed branch
- **THEN** the handoff record for the transition is not published
- **AND** the worker exits non-zero stating the persistence failure
