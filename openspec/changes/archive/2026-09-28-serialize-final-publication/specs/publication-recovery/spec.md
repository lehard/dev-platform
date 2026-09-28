## MODIFIED Requirements

### Requirement: Existing exact-head PRs resume before first-publication stale-base rejection

A supported finish invocation SHALL distinguish a current task branch from one that is behind or diverged from freshly observed authoritative main before starting expensive validation. A first publication still obeys the platform's fresh-base safety preconditions. For an exact-head PR admitted to the source repository's publication queue, ordinary main advancement by a preceding queued change SHALL be handled by the queue coordinator rather than requiring the waiting agent to reconcile and revalidate solely for that advancement. A PR outside that queue retains explicit reconciliation behavior. Changed task content, overlapping relevant base changes, unknown queue identity or a failed coordinator check SHALL fail closed to explicit recovery.

#### Scenario: Base advances while exact PR is waiting

- **GIVEN** an open exact-head task PR exists outside the central publication queue
- **AND** the base branch advances after the PR was created
- **WHEN** finish is invoked again
- **THEN** it stops before expensive validation and points to the supported reconcile operation
- **AND** reconciliation preserves the same PR branch without force-push or rebase
- **AND** validation must rerun for the resulting descendant head before publication resumes

#### Scenario: New stale branch has never been published

- **GIVEN** no exact-head PR exists for local task commit A
- **AND** A does not satisfy the platform's first-publication fresh-base prerequisite
- **WHEN** finish attempts first publication
- **THEN** publication remains blocked until the branch is explicitly reconciled and revalidated

#### Scenario: Queued PR waits while main advances

- **GIVEN** an exact-head task PR is admitted to the publication queue
- **AND** another nonoverlapping queued PR merges first
- **WHEN** waiting task finish/status runs
- **THEN** it observes the durable queue state without starting expensive validation or demanding agent-side reconcile merely for that base advancement
- **AND** the coordinator proves and checks the updated candidate before its protected merge.

#### Scenario: Queued candidate changes outside coordinator control

- **WHEN** the queued PR head changes from the admitted or proven coordinator-produced head
- **THEN** old queue admission does not authorize publication
- **AND** fresh local validation and a new exact-head admission are required.
