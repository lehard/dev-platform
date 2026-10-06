## MODIFIED Requirements

### Requirement: Reviewer runtime readiness is proven before review perspectives launch

Before launching any independent review perspective, the platform SHALL prove that the selected reviewer runtime is usable on the current host and account with the exact selected model, using one bounded probe launched through the same read-only adapter. When readiness cannot be proven, the platform SHALL record the review as unavailable with a concrete actionable limitation and SHALL NOT launch the perspectives. The platform SHALL expose the same readiness check as a standalone command. It SHALL NOT substitute another model or provider unless configuration declares an ordered provider list; then each configured provider is probed in order, the review records the requested provider, the executed provider and the fallback reason, and when every configured provider is unavailable the candidate becomes blocked-retryable and is retried automatically rather than escalated to a human.

#### Scenario: Reviewer CLI is not logged in or cannot be executed
- **GIVEN** a required independent review
- **AND** the resolved reviewer binary is missing or its probe exits unsuccessfully
- **WHEN** the review runs
- **THEN** both perspectives are recorded as unavailable with a limitation naming the runtime's bounded error and the next step
- **AND** no review perspective is launched
- **AND** the candidate does not pass the review gate

#### Scenario: Selected model is not available to the current account
- **GIVEN** the probe with the exact selected model is rejected by the runtime
- **WHEN** readiness is evaluated
- **THEN** the limitation identifies the provider and model and directs the operator to change the binding or the account
- **AND** no unconfigured model or provider is tried

#### Scenario: Readiness is checked before implementation
- **WHEN** an agent runs the standalone readiness command after routing a managed task
- **THEN** it receives the resolved provider, model and binary with a ready or not-ready result and an actionable limitation
- **AND** no review evidence is written

## ADDED Requirements

### Requirement: Developer completion is a handoff at a verified PR

For a coordinator-managed candidate, developer completion SHALL end at a handoff: selected checks and semantic verification evidence for the still-active change, an exact-head PR, a developer friction checkpoint bound to the handoff head, admission to the coordinator and release of the developer's writer claim. Handoff SHALL NOT wait for review, CI, main movement or merge.

#### Scenario: Developer finishes
- **WHEN** the developer runs finish for a coordinator-managed candidate
- **THEN** the PR exists, the candidate is review-pending and the developer session is free

### Requirement: Review and repair run as candidate jobs

Independent Review for a coordinator-managed candidate SHALL run as a job on the exact PR head with the existing fresh-context, read-only and two-perspective guarantees. A fixable finding SHALL produce a bounded repair job executed without the original developer; changed task content SHALL make review stale. A proposal to reject a material finding, or exhausted repair rounds, SHALL move the candidate to blocked-escalation.

Jobs SHALL retain the originating task's resolved reviewer provider or explicitly configured ordered providers across repair and retry. Workers SHALL NOT substitute their local route. Unavailable review SHALL retry at most three consecutive attempts, then remain blocked-retryable with unavailable evidence and no automatic job. Publication SHALL leave review-owned retry states untouched. Workers SHALL confirm unexpired ownership of the exact job and originating head immediately before push and candidate advancement; lost ownership SHALL abandon without further side effects. Repair SHALL reject lifecycle evidence paths at any depth, including evidence directories. A trusted repair completion published before interrupted advancement SHALL recover on the next run without rerunning the writer.

#### Scenario: Finding is repaired
- **GIVEN** review reports a fixable material finding
- **WHEN** the repair job changes task content
- **THEN** review runs again for the new identity

#### Scenario: Rejection proposed
- **WHEN** a worker proposes rejecting a material finding
- **THEN** the candidate waits for a human decision

### Requirement: Gate evidence is reused for unchanged task content

Required-check, selected-check and review evidence SHALL be bound to the task-content identity it verified and SHALL be reused by later lifecycle steps when that identity is unchanged; changed or unprovable identity SHALL require the gate again.

#### Scenario: Bookkeeping commit after review
- **WHEN** only lifecycle evidence paths change
- **THEN** review and check evidence remain valid
