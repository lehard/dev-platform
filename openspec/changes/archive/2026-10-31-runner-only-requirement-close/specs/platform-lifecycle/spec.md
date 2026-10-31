## ADDED Requirements

### Requirement: Only post-merge jobs record the Requirement retrospective and close the Requirement

With the coordinator queue enabled, the Requirement retrospective checkpoint and the terminal close of a Requirement SHALL be recorded only by the post-merge retrospective and terminal-reconciliation jobs, after the last mandatory child or the composition PR merged. Developer commands SHALL NOT require that checkpoint or close the parent. Without the queue, the same functions run in the developer session.

#### Scenario: One child merged
- **WHEN** the only child PR of a Requirement merges
- **THEN** its post-merge retrospective job records the task and Requirement checkpoints
- **AND** its terminal-reconciliation job closes the child and the Requirement without a developer action

#### Scenario: Several children merged through a composition
- **WHEN** the composition PR merges
- **THEN** the post-merge jobs record the Requirement checkpoint and then close the Requirement

#### Scenario: Developer publication
- **WHEN** a developer publishes a child or a composition
- **THEN** no Requirement checkpoint is required and the parent stays open

### Requirement: A stored pre-merge retrospective job fails explicitly

A lifecycle record or job of kind `retrospective` with phase `pre-merge` SHALL NOT be derived or offered as work. Deriving such a record SHALL fail naming the PR, so a candidate created before this change is noticed instead of silently skipped.

#### Scenario: Old pre-merge job on an open composition
- **WHEN** a worker or the overview derives a composition PR whose record carries a pre-merge retrospective job
- **THEN** derivation fails naming the PR and no job is offered

## MODIFIED Requirements

### Requirement: Composition review covers only cross-child properties

The Requirement candidate SHALL receive a composition review covering cross-child contract compatibility, duplicated or conflicting behavior and the Requirement-level outcome. Child content whose task-content identity is unchanged since its own review SHALL NOT be fully re-reviewed.

#### Scenario: Unchanged children
- **WHEN** all child identities are unchanged since their reviews
- **THEN** composition review examines only interactions and the Requirement outcome

#### Scenario: Reviewed contributions extend shared files
- **GIVEN** an earlier child head and its reviewed identity are preserved in the candidate ancestry
- **WHEN** a later reviewed contribution or composition repair extends a file changed by that child
- **THEN** composition validates each original identity at its preserved child head and reviews the resulting composition content
- **AND** it does not require each earlier blob to equal the final tree

#### Scenario: A repaired contribution regains its gates
- **WHEN** a contribution passes fresh review after a content-changing repair
- **THEN** the coordinator reruns selected checks and requires fresh semantic verification bound to the repaired identity before offering contribution integration
- **AND** stale semantic verification blocks finalization pending a refreshed developer receipt; the old PASS receipt is never automatically rebound
- **AND** the contribution remains active until composition finalization

#### Scenario: A finalized composition receives its parent retrospective
- **WHEN** composition finalization completes
- **THEN** no pre-merge retrospective job is offered and full checks and admission do not wait for a Requirement checkpoint
- **AND** the parent retrospective is recorded by the post-merge retrospective job after the composition PR merges

#### Scenario: Archived composition artifacts remain reviewable
- **WHEN** composition review runs after children have been archived
- **THEN** canonical identity paths are resolved to their actual archived Git locations in the review diff

#### Scenario: Interrupted composition archive push resumes
- **WHEN** a validated composition finalization push succeeds before its state transition is recorded
- **THEN** recovery re-offers finalization on the recovered head to restore the finalization gate

#### Scenario: Failed contribution checks offer repair
- **WHEN** required contribution checks fail before integration
- **THEN** the publication queue records repair-pending and publishes a runnable repair job discoverable by workers

#### Scenario: Composition checks cannot access coordinator credentials
- **WHEN** composition validation executes candidate-controlled commands
- **THEN** commands run with credential_free_env, an isolated home and stdin disconnected
- **AND** GH_TOKEN, GITHUB_TOKEN, SSH_AUTH_SOCK and the operator HOME are unavailable

#### Scenario: Resume waits for coordinator-owned contributions
- **WHEN** a Requirement resumes while a child has a trusted developer handoff in review, repair, finalization or integration
- **THEN** it reports that child as in flight and does not restart it or reacquire its writer claim

#### Scenario: Refreshed semantic verification can be admitted
- **GIVEN** the same contribution's prior proven head stopped in blocked-retryable for fresh semantic verification
- **WHEN** the developer publishes a new exact head with fresh identity-bound handoff gates
- **THEN** admission creates a new queue slot and offers review
- **AND** other changed-head admissions retain their exact-head refusal

#### Scenario: Parent post-merge jobs include child obligations
- **WHEN** the exact Requirement candidate merges
- **THEN** its bounded retrospective and cleanup jobs process every child source branch, PR and head from the committed manifest before completing the parent obligation
- **AND** interruption repeats idempotent operations and a refused child obligation blocks completion

#### Scenario: Historical PRs do not consume the queue bound
- **WHEN** a repository has at least one hundred unrelated historical PRs
- **THEN** queue inventory remains available and applies its bound only to queued candidates
- **AND** a merged queued contribution remains discoverable for interrupted manifest publication recovery

#### Scenario: Composition review uses explicit providers
- **WHEN** composition review is offered from the integration checkout
- **THEN** the job carries configured providers or providers from the mandatory children's originating routes
- **AND** it does not resolve the integration checkout's current task route

#### Scenario: Hosted harness push authenticates without writer credentials
- **WHEN** a disposable harness clone publishes a Requirement branch or manifest over GitHub HTTPS
- **THEN** that push uses the coordinator token through a process-scoped extraheader for the clone's exact origin
- **AND** missing credentials fail explicitly and the token is absent from command arguments, checkout configuration and error output
