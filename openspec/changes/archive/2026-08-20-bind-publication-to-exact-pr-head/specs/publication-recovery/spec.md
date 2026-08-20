## ADDED Requirements

### Requirement: Exact-head publication identity remains unambiguous across reused branch names

For `harness_mode=platform` and `publish_mode=pr`, branch name SHALL be only a discovery hint. The publication lifecycle SHALL identify the current publication object by repository, configured base branch, head branch, and exact expected head SHA. Discovery SHALL remain correct when historical pull requests reuse the same head branch name.

Once an exact pull request is selected or created, required-check reads, merge requests, merge-state reads, recovery, and terminal reconciliation SHALL use a stable PR number or URL together with the same expected head SHA. A branch-name-only lookup, command exit code, or stale merged PR SHALL NOT authorize destructive cleanup or terminal success.

#### Scenario: Historical merged PR and current exact PR share a branch name

- **GIVEN** an older PR for branch `X` is `MERGED` at head A
- **AND** branch `X` is later reused at head B
- **AND** GitHub has an exact PR for B targeting the configured base branch
- **WHEN** publication state for B is discovered
- **THEN** the lifecycle selects the PR whose `headRefOid` is B
- **AND** the historical PR at A cannot authorize checks, merge recovery, cleanup, or terminal status for B

#### Scenario: Historical merged PR exists but the current head has no PR yet

- **GIVEN** an older PR for branch `X` is `MERGED` at head A
- **AND** the current validated branch head is B
- **AND** no exact PR for B exists
- **WHEN** publication of B starts
- **THEN** the historical PR at A is treated only as historical state
- **AND** the lifecycle creates or discovers an exact PR for B or fails closed
- **AND** it does not delete the remote branch, reconcile local main, finish board/worktree state, or report terminal success for B

#### Scenario: Merge command succeeds but exact merge proof is not available

- **GIVEN** the lifecycle requested merge for stable PR P at expected head B
- **WHEN** the merge command exits zero
- **BUT** GitHub does not confirm both `state == MERGED` and `headRefOid == B` for P
- **THEN** cleanup and terminal reconciliation remain blocked and resumable

#### Scenario: Merge command exits non-zero after possible server-side success

- **GIVEN** the lifecycle requested merge for stable PR P at expected head B
- **WHEN** the merge command exits non-zero
- **THEN** recovery may continue only if GitHub confirms both `state == MERGED` and `headRefOid == B` for P
- **AND** a merged PR for another head cannot be used as recovery evidence

#### Scenario: Exact PR head changes after validation

- **GIVEN** stable PR P was selected for expected head B
- **WHEN** GitHub reports a different `headRefOid` before terminal merge confirmation
- **THEN** the lifecycle fails closed
- **AND** the changed head requires normal revalidation before publication can continue

#### Scenario: Restart observes the exact head already merged

- **GIVEN** stable PR P for expected head B was already merged
- **WHEN** publication recovery runs again
- **THEN** the lifecycle may resume from that exact merged evidence
- **AND** performs only the remaining safe reconciliation/cleanup idempotently
