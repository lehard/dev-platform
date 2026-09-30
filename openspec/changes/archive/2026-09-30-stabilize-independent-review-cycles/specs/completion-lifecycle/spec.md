## ADDED Requirements

### Requirement: Reviewer runtime readiness is proven before review perspectives launch

Before launching any independent review perspective, the platform SHALL prove that the selected reviewer runtime is usable on the current host and account with the exact selected model, using one bounded probe launched through the same read-only adapter. When readiness cannot be proven, the platform SHALL record the review as unavailable with a concrete actionable limitation and SHALL NOT launch the perspectives. The platform SHALL expose the same readiness check as a standalone command. It SHALL NOT substitute another model or provider.

#### Scenario: Reviewer CLI is not logged in or cannot be executed
- **GIVEN** a required independent review
- **AND** the resolved reviewer binary is missing or its probe exits unsuccessfully
- **WHEN** the review runs
- **THEN** both perspectives are recorded as unavailable with a limitation naming the runtime's bounded error and the next step
- **AND** no review perspective is launched
- **AND** archive stops before expensive validation

#### Scenario: Selected model is not available to the current account
- **GIVEN** the probe with the exact selected model is rejected by the runtime
- **WHEN** readiness is evaluated
- **THEN** the limitation identifies the provider and model and directs the operator to change the binding or the account
- **AND** no other model or provider is tried

#### Scenario: Readiness is checked before implementation
- **WHEN** an agent runs the standalone readiness command after routing a managed task
- **THEN** it receives the resolved provider, model and binary with a ready or not-ready result and an actionable limitation
- **AND** no review evidence is written

### Requirement: Reviewer context excludes lifecycle-generated evidence

The candidate diff and prompt given to an independent reviewer SHALL cover exactly the task-owned content that the review task-content identity binds. Lifecycle receipts, review evidence and archive-derived spec materialization SHALL NOT be presented as candidate content, and the request SHALL record which lifecycle paths were excluded.

#### Scenario: Previous review evidence is committed in the candidate
- **GIVEN** the candidate branch contains committed review requests, reports, dispositions, automated-check evidence or a verification receipt
- **WHEN** a reviewer is launched
- **THEN** the reviewer diff omits those paths
- **AND** the prompt identifies them as lifecycle evidence that is not reviewed

#### Scenario: Unchanged final candidate completes with one review round
- **GIVEN** a required managed change whose independent review is ready
- **WHEN** archive, lifecycle evidence commits and finish follow without a task-owned content change
- **THEN** no additional review round is launched
- **AND** the existing review evidence satisfies the gate

#### Scenario: Task-owned content changes after review
- **WHEN** any path included in the review identity changes
- **THEN** the review evidence is stale and a fresh review is required
