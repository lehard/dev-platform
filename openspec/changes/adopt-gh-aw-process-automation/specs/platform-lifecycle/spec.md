## MODIFIED Requirements

### Requirement: Deliberate learning promotion

Platform friction SHALL keep raw evidence machine-local by default, while high-signal sanitized friction candidates SHALL be routed automatically to the appropriate GitHub process-issue backlog during supported lifecycle processing instead of depending on remembered routine manual promotion. Routing SHALL sanitize credential-like content and arbitrary raw evidence, deduplicate repeated occurrences with a stable non-secret fingerprint, and preserve a durable local fallback when GitHub routing is unavailable.

Process/friction issues SHALL remain evidence/inbox state. They SHALL NOT automatically create Development Backlog tasks, materialize OpenSpec changes, dispatch executors or start remediation. Converting process evidence into managed work requires separate explicit human fixation intent through the managed-task authoring contract.

#### Scenario: Reusable friction is promoted

- **WHEN** an agent identifies a recurring platform-level problem through a high-signal supported friction event
- **THEN** only sanitized structured evidence is sent to the central platform inbox through the routing contract
- **AND** raw evidence remains machine-local by default

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

### Requirement: Meaningful friction capture requires a post-task retrospective

For a non-trivial platform-owned task, terminal completion SHALL require a bounded post-task process retrospective before the friction completion checkpoint is considered resolved. The retrospective SHALL be a distinct semantic review step over the substantive task execution, not merely a choice of `none` or one event id.

The retrospective SHALL inspect available task-local evidence and the agent's execution context for high-signal process friction, including user corrections, repeated substantive failures/retries, manual workarounds, safety near-misses, false task premises, undocumented invariants, missing automation/documentation, tooling/auth/worktree/Git/OpenSpec/CI/lifecycle friction, avoidable repeated work, and problems noticed but left unresolved.

For each candidate, the retrospective SHALL distinguish:
- friction already resolved as part of the current task;
- friction already represented by an existing recorded event/process issue;
- new meaningful unresolved and unrecorded friction.

Only the third class SHALL create new friction evidence. A single retrospective result SHALL support zero or more recorded event references. `none` SHALL be valid only when the retrospective was actually completed and yielded zero new meaningful unresolved/unrecorded findings.

The retrospective completion evidence SHALL be fresh for the current task execution state. The platform SHALL reuse existing task-local provenance/exact execution identity where possible so stale checkpoint state from earlier work cannot silently satisfy changed or new work. The implementation SHALL NOT introduce a parallel task database or second lifecycle state machine solely for this purpose.

Supported machine-detectable lifecycle/process failures SHOULD continue to record friction directly when observed rather than waiting for the final retrospective.

#### Scenario: Multiple new semantic findings are discovered

- **GIVEN** a non-trivial platform-owned task contains two or more distinct high-signal semantic friction conditions
- **AND** those conditions are unresolved and not already recorded
- **WHEN** the post-task retrospective runs
- **THEN** each meaningful condition is recorded as structured friction evidence
- **AND** the completion result can reference all resulting event ids
- **AND** the agent is not forced to choose only one finding

#### Scenario: Clean task completes retrospective with no findings

- **WHEN** the required post-task retrospective runs
- **AND** it finds no new meaningful unresolved/unrecorded friction
- **THEN** the retrospective result records zero findings
- **AND** `none` is accepted without creating process-issue noise

#### Scenario: Candidate was already resolved or already recorded

- **GIVEN** a candidate friction was fixed during the task or is already represented by existing friction/process evidence
- **WHEN** the retrospective classifies the candidate
- **THEN** it does not create a duplicate new event solely to satisfy completion
- **AND** any remaining new unresolved candidates are still processed normally

#### Scenario: Retrospective is omitted

- **WHEN** a non-trivial platform-owned task reaches the authoritative completion boundary without a current retrospective result
- **THEN** terminal completion is refused
- **AND** the agent receives an actionable instruction to perform the retrospective
- **AND** the lifecycle does not invent `none` on the agent's behalf

#### Scenario: Retrospective evidence is stale

- **GIVEN** retrospective/checkpoint evidence belongs to an earlier task execution state
- **AND** substantive task state has since changed according to the platform's supported freshness identity
- **WHEN** terminal completion is attempted
- **THEN** the stale evidence does not satisfy the completion invariant
- **AND** a fresh retrospective is required

#### Scenario: Deterministic lifecycle failure occurs before retrospective

- **WHEN** a supported lifecycle component detects an allow-listed machine-classifiable process failure or safety near-miss
- **THEN** it records the structured local friction event directly with bounded available context
- **AND** the later retrospective may recognize that event as already recorded rather than duplicating it

#### Scenario: Routing fails after positive retrospective

- **WHEN** the retrospective has valid local event references but GitHub routing is temporarily unavailable
- **THEN** terminal completion may continue if all deterministic delivery requirements are otherwise satisfied
- **AND** the events remain pending for later routing retry
- **AND** the retrospective receipt remains truthful about the local findings

#### Scenario: Agent reports terminal completion

- **WHEN** a non-trivial platform-owned task reaches terminal completion
- **THEN** the final agent report states that the post-task retrospective was completed
- **AND** it either identifies the recorded findings/evidence or states that no new unresolved/unrecorded meaningful friction was found
- **AND** the human user is not required to send a separate natural-language reminder to trigger this analysis
