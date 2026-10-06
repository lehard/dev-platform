## MODIFIED Requirements

### Requirement: Shared candidates grow append-only and are draft until complete

A shared Requirement candidate manifest SHALL list the expected mandatory changes and the reviewed child contributions integrated so far. Where source/coordinator publication is enabled, child contributions SHALL reach the candidate through contribution PRs targeting the Requirement integration branch and SHALL be merged into it by the coordinator after their own checks, verification and review. An incomplete candidate SHALL be published only as a draft PR on its stable branch and manifest path. A new manifest revision SHALL keep earlier children as an exact prefix with identical heads and SHALL be pushed only as a fast-forward. Marking the PR ready, arming merge, publication-queue admission and terminal reconciliation SHALL require a complete manifest, composition-level review of cross-child properties, a single finalization of all children, the Requirement retrospective checkpoint and full checks on the exact final head.

#### Scenario: Later child is appended

- **GIVEN** a draft candidate PR exists for the first verified child
- **WHEN** the next child is ready
- **THEN** its exact delta is added as new commits on the same branch and the manifest is extended
- **AND** the same PR is updated by fast-forward push without a force push or duplicate

#### Scenario: Divergent or reordered growth is refused

- **GIVEN** an existing candidate branch
- **WHEN** a revision changes, removes or reorders an earlier child, a child head changed, or the branch is not a fast-forward
- **THEN** publication stops before any push or PR mutation naming the exact boundary

#### Scenario: Interrupted run resumes

- **GIVEN** a draft or ready candidate PR already exists for the exact branch
- **WHEN** the supervisor is rerun
- **THEN** it resumes that branch and PR without creating another PR or candidate

#### Scenario: Completion applies the final gates

- **GIVEN** every mandatory child is present
- **WHEN** the candidate is made ready
- **THEN** the retrospective checkpoint exists and full checks pass on the exact final head before the existing protected merge path runs

## ADDED Requirements

### Requirement: Independent children execute in parallel as contributions

Where source/coordinator publication is enabled, children of a multi-child Requirement without unmet dependencies SHALL be able to start and proceed in parallel, each as a contribution PR to the Requirement integration branch with its own checks, verification, review and repair. A dependent child SHALL start from the integration branch after its predecessors are integrated. Downstream projects SHALL retain the existing archived-child multi-child path. A single-child Requirement SHALL use its child PR against main; a coordinator-managed child SHALL publish while active for review before finalization archives it.

#### Scenario: Two independent children
- **WHEN** a Requirement has two children without dependencies
- **THEN** both can be developed and reviewed at the same time

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
- **THEN** the coordinator offers an exact-head pre-merge retrospective job
- **AND** that job records the Requirement checkpoint before full checks and admission without a manual happy-path checkpoint

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
