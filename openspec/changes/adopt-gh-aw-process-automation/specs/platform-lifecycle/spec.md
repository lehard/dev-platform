## MODIFIED Requirements

### Requirement: Deliberate learning promotion

Platform friction SHALL keep raw evidence machine-local by default, but high-signal sanitized friction candidates SHALL be routed automatically to the appropriate GitHub issue backlog during supported lifecycle processing instead of depending on remembered routine manual promotion. Routing SHALL sanitize credential-like content and arbitrary raw evidence, deduplicate repeated occurrences, and preserve a durable local fallback when GitHub routing is unavailable.

#### Scenario: Reusable friction is promoted

- **WHEN** an agent identifies a recurring platform-level problem and an authenticated promotion is explicitly requested
- **THEN** only sanitized structured evidence is sent to the central platform inbox

#### Scenario: Platform-level friction is captured

- **WHEN** an agent or deterministic lifecycle hook records a high-signal event with `scope=platform`
- **THEN** the platform stores the raw structured event locally
- **AND** automatically attempts to create or update a sanitized fingerprinted issue in the configured platform repository
- **AND** does not require the human operator to remember a separate `promote` command

#### Scenario: Project-level friction is captured

- **WHEN** a high-signal event has `scope=project`
- **THEN** the platform automatically attempts to create or update the sanitized fingerprinted issue in the current project repository
- **AND** does not route that project-specific issue to the central platform backlog solely because the platform provides the tooling

#### Scenario: Similar friction repeats

- **GIVEN** an open issue already contains the stable sanitized fingerprint for the event class
- **WHEN** the same friction recurs
- **THEN** routing updates the existing issue with a bounded sanitized occurrence rather than creating a duplicate issue

#### Scenario: GitHub routing is unavailable

- **WHEN** authentication, network or GitHub API availability prevents issue routing
- **THEN** the local event remains pending for a later supported retry
- **AND** no raw credential-bearing evidence is printed or uploaded
- **AND** an otherwise safe task is not reclassified as failed solely because process telemetry could not be routed

## ADDED Requirements

### Requirement: Meaningful friction capture is a completion invariant

For a non-trivial platform-managed task, completion SHALL include an explicit friction checkpoint so meaningful user corrections, repeated failures, safety near-misses, workarounds, false task premises, avoidable CI/lifecycle failures or excessive retries cannot be omitted merely because the agent forgot to record them. Machine-detectable lifecycle failures SHOULD record friction directly without relying on model judgment.

#### Scenario: Agent encountered meaningful model-observed friction

- **WHEN** a non-trivial task reaches completion and one or more high-signal conditions occurred
- **THEN** at least one corresponding structured friction event exists before completion is reported
- **AND** the event proceeds through automatic sanitized routing

#### Scenario: No meaningful friction occurred

- **WHEN** the completion checkpoint finds no high-signal friction
- **THEN** the task may complete without creating a friction issue
- **AND** the checkpoint itself does not create issue noise

#### Scenario: Deterministic lifecycle failure occurs

- **WHEN** a supported lifecycle component detects a machine-classifiable process failure or safety near-miss
- **THEN** it records the friction event directly with the available sanitized classification/context
- **AND** does not depend on a later natural-language agent memory step to preserve the event
