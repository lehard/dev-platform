## MODIFIED Requirements

### Requirement: Deliberate learning promotion

Platform friction SHALL keep raw evidence machine-local by default, while high-signal sanitized friction candidates SHALL be routed automatically to the appropriate GitHub process-issue backlog during supported lifecycle processing instead of depending on remembered routine manual promotion. Routing SHALL sanitize credential-like content and arbitrary raw evidence, deduplicate repeated occurrences with a stable non-secret fingerprint, and preserve a durable local fallback when GitHub routing is unavailable.

Process/friction issues SHALL remain evidence/inbox state. They SHALL NOT automatically create Development Backlog tasks, materialize OpenSpec changes, dispatch executors or start remediation. Converting process evidence into managed work requires separate explicit human fixation intent through the managed-task authoring contract.

#### Scenario: Platform-level friction is captured

- **WHEN** an agent or supported deterministic lifecycle hook records a high-signal event with `scope=platform`
- **THEN** the platform stores the raw structured event locally
- **AND** automatically attempts to create or update a sanitized fingerprinted issue in the configured platform repository
- **AND** does not require the human operator to remember a separate `promote` command

#### Scenario: Project-level friction is captured

- **WHEN** a high-signal event has `scope=project`
- **THEN** the platform automatically attempts to create or update the sanitized fingerprinted issue in the normalized current project repository
- **AND** does not route that project-specific issue to the central platform inbox solely because the platform provides the tooling

#### Scenario: Similar friction repeats

- **GIVEN** an open process issue already contains the stable sanitized fingerprint for the event class
- **WHEN** the same friction class recurs
- **THEN** routing updates that issue with a bounded sanitized occurrence rather than creating a duplicate issue

#### Scenario: Raw evidence contains sensitive context

- **WHEN** a recorded friction event contains arbitrary raw evidence, credential-like text or machine-local details
- **THEN** those raw fields remain machine-local by default
- **AND** the GitHub representation contains only bounded sanitized structured fields allowed by the routing contract

#### Scenario: GitHub routing is unavailable

- **WHEN** authentication, network or GitHub API availability prevents issue routing
- **THEN** the local event remains pending for a later supported lifecycle retry
- **AND** no raw credential-bearing evidence is printed or uploaded
- **AND** an otherwise safe task is not reclassified as failed solely because process telemetry could not be routed

#### Scenario: Process evidence looks ready for remediation

- **WHEN** a process issue or cloud review recommends a reusable fix
- **THEN** the recommendation remains advisory process evidence
- **AND** no Development Backlog issue or OpenSpec change is created until the human explicitly requests fixation through the managed-task authoring path

## ADDED Requirements

### Requirement: Meaningful friction capture is a completion invariant

For a non-trivial platform-owned task, completion SHALL include one explicit friction checkpoint so meaningful user corrections, repeated failures, safety near-misses, workarounds, false task premises, avoidable CI/lifecycle failures or excessive retries cannot be omitted merely because the agent forgot to record them. The checkpoint SHALL reuse the ordinary platform lifecycle rather than require a separate agent-specific hook or background state machine.

Supported machine-detectable lifecycle/process failures SHOULD record friction directly without relying on model judgment.

#### Scenario: Agent encountered meaningful model-observed friction

- **WHEN** a non-trivial platform-owned task reaches completion and one or more high-signal semantic conditions occurred
- **THEN** the completion checkpoint resolves to a corresponding structured friction event reference before completion is reported
- **AND** the event proceeds through automatic sanitized routing

#### Scenario: No meaningful friction occurred

- **WHEN** the completion checkpoint resolves to `friction: none`
- **THEN** the task may complete without creating a friction issue
- **AND** the checkpoint itself does not create issue noise

#### Scenario: Completion checkpoint is omitted

- **WHEN** a non-trivial platform-owned task reaches the completion boundary without an explicit friction checkpoint result
- **THEN** the lifecycle refuses to report terminal completion until the checkpoint is resolved
- **AND** it does not invent a friction event on the agent's behalf

#### Scenario: Deterministic lifecycle failure occurs

- **WHEN** a supported lifecycle component detects an allow-listed machine-classifiable process failure or safety near-miss
- **THEN** it records the structured local friction event directly with bounded available context
- **AND** does not depend on a later natural-language reminder to preserve the observation

#### Scenario: Routing fails after checkpoint resolution

- **WHEN** a valid positive friction checkpoint has recorded its local event but GitHub routing is temporarily unavailable
- **THEN** completion may continue if all deterministic delivery requirements are otherwise satisfied
- **AND** the event remains pending for later routing retry
