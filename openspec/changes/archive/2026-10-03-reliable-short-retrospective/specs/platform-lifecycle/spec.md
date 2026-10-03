# platform-lifecycle Specification Delta

## MODIFIED Requirements

### Requirement: Meaningful friction capture is a completion invariant

For a non-trivial platform-owned task, terminal completion SHALL include a bounded post-task process retrospective so meaningful user corrections, repeated failures, safety near-misses, workarounds, false task premises, avoidable CI/lifecycle failures, excessive retries or other high-signal unresolved process problems cannot be omitted merely because the agent forgot to record them. The retrospective SHALL run before the final friction checkpoint and SHALL reuse the ordinary platform lifecycle rather than require a separate agent-specific hook or background state machine.

The retrospective SHALL distinguish problems already fixed during the task, problems already represented by existing friction/process evidence, and new meaningful unresolved/unrecorded findings. One retrospective MAY legitimately produce `0..N` new friction events. `none` SHALL mean that this bounded retrospective ran and found no new meaningful unresolved/unrecorded findings; a bare checkpoint call without a current retrospective result is insufficient.

The retrospective/checkpoint result SHALL be bound to current task execution state sufficiently to prevent a stale result from silently completing changed work. Supported machine-detectable lifecycle/process failures SHOULD continue recording friction directly without relying on model judgment.

The bounded post-task review SHALL inspect the factual execution path, including meaningful successful manual workarounds, non-default or override actions, manual state changes, recurrences of already open process issues, and observed material drift even when another operator, runtime or lifecycle owns the state. Harmless deviations are not friction. A known open issue does not dispose of a new occurrence: the recurrence SHALL be preserved through the existing friction/process issue path. A clean path retains a concise `none` checkpoint.

An evidence source that is unreadable or only partially readable SHALL be named in the review and SHALL NOT be reported as the absence of problems; a checkpoint over such a source SHALL require an explicit acceptance of that gap, recorded in the receipt.

#### Scenario: Several unresolved semantic frictions occurred

- **WHEN** a non-trivial platform-owned task reaches completion with two or more distinct high-signal semantic conditions that remain unresolved and unrecorded
- **THEN** the retrospective records or links all corresponding new friction events before completion is reported
- **AND** the completion result is not forced to choose only one event

#### Scenario: No meaningful friction occurred

- **WHEN** the bounded retrospective completes with zero new meaningful unresolved/unrecorded findings
- **THEN** the current completion checkpoint may resolve to `friction: none`
- **AND** no friction issue is created merely for the clean result

#### Scenario: Retrospective is omitted

- **WHEN** a non-trivial platform-owned task reaches the completion boundary without a current retrospective result
- **THEN** the lifecycle refuses terminal completion with an actionable instruction to perform the bounded review
- **AND** it does not invent a friction event on the agent's behalf

#### Scenario: Evidence source is degraded

- **GIVEN** the friction log has unreadable or malformed content
- **WHEN** the agent records `none` without accepting the named gap
- **THEN** the checkpoint is refused and names the degraded source
- **AND** an explicit acceptance of that gap is stored in the receipt

#### Scenario: Stale retrospective is reused

- **GIVEN** a valid retrospective/checkpoint existed for an earlier task execution state
- **WHEN** relevant task state changes before terminal completion
- **THEN** the old result does not satisfy the completion invariant
- **AND** a current retrospective is required

#### Scenario: Deterministic lifecycle failure occurs

- **WHEN** a supported lifecycle component detects an allow-listed machine-classifiable process failure or safety near-miss
- **THEN** it records the structured local friction event directly with bounded available context
- **AND** does not depend on a later natural-language reminder to preserve the observation

#### Scenario: Routing fails after checkpoint resolution

- **WHEN** a valid positive friction checkpoint has recorded its local event but GitHub routing is temporarily unavailable
- **THEN** completion may continue if all deterministic delivery requirements are otherwise satisfied
- **AND** the event remains pending for later routing retry

#### Scenario: Successful override and known issue recur

- **GIVEN** an agent uses a non-default override to complete a task and the same process defect already has an open issue
- **WHEN** it performs the retrospective
- **THEN** it records the meaningful recurrence as a new occurrence through the existing friction router
- **AND** no user prompt is required to surface it.

## ADDED Requirements

### Requirement: Friction events carry resolvable task attribution

New friction events SHALL record an explicit task when given, otherwise the current task branch, and SHALL mark an event recorded with neither as unattributed; an integration checkout or unknown branch SHALL NOT be assumed to be a task. Retrospective selection SHALL attribute a legacy event whose task is empty by its recorded branch or source issue without rewriting or duplicating history. An event that cannot be attributed SHALL be reported as an explicit ambiguity in review and checkpoint output, SHALL NOT be assigned to the task under review, and SHALL NOT disappear silently.

#### Scenario: Event lost its task but kept branch and source issue

- **GIVEN** a recorded event has an empty task and a branch equal to the task under review
- **WHEN** the retrospective selects mandatory signals
- **THEN** the event is included as an inferred-attribution signal and must be explained
- **AND** the stored event is not modified

#### Scenario: Event cannot be attributed

- **GIVEN** a recent event has an empty task and no usable branch or source issue
- **WHEN** a retrospective runs
- **THEN** the event is listed as ambiguous attribution
- **AND** it is not required to be explained by, nor assigned to, the task under review

### Requirement: Retrospective uses a short shared template with bounded project additions

The review-path SHALL present a short shared template covering what happened and its basis, the confirmed cause kept apart from a hypothesis (an unknown cause is acceptable), the fix kept apart from a workaround, repeats and remaining problems, and the required action with a verifiable result or the reason for none. A project MAY add up to five questions in a project-owned file, each optionally limited to changed paths; questions beyond five SHALL be ignored with a report, and a missing or invalid file SHALL leave the shared path working. Project questions SHALL NOT be mandatory for every task and SHALL NOT replace the shared template.

#### Scenario: Project adds a path-scoped question

- **GIVEN** a project question is limited to a path pattern
- **WHEN** the task changes a matching file
- **THEN** the review-path presents the question after the shared template
- **AND** a task that changes no matching file does not see it

#### Scenario: Project has no additions

- **WHEN** the project-owned file is absent
- **THEN** the shared template alone is presented and completion is unaffected
