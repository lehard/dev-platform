## MODIFIED Requirements

### Requirement: Coordinator verifies the actual current-base candidate

One repository-owned coordinator SHALL process the next eligible PR after the prior merge, prepare its exact head on current main without rewriting task-owned content, require protected GitHub checks on that actual candidate, and request merge with an expected-head guard. An ordinary unrelated preceding queue merge SHALL NOT require each waiting task agent to manually reconcile and repeat a full local validation pass. Required CI and branch protection SHALL NOT be bypassed. Base actualization SHALL belong to this integration contour alone, after finalization: the coordinator SHALL merge a clean result with current main automatically, SHALL run required CI on the actual merged head, and SHALL offer integration repair on a real conflict or a failing required check. Neither candidate finalization nor an advance of `main` by other PRs between review and finalization SHALL require developer involvement for a reviewed candidate whose task content is unchanged.

#### Scenario: Earlier queued PR advances main

- **GIVEN** candidate B waits behind candidate A and their task paths do not overlap
- **WHEN** A merges
- **THEN** B is prepared and checked on the new main by the coordinator
- **AND** B merges only after its actual updated head satisfies required checks.

#### Scenario: Main or candidate changes materially

- **WHEN** task-owned content changes, or a merge conflict prevents exact preparation
- **THEN** the coordinator does not merge under old evidence
- **AND** the candidate has an explained block or an integration-repair job and a supported recovery action.

#### Scenario: Required check fails or main moves during final check

- **WHEN** the required check fails, or main advances before the guarded merge
- **THEN** the coordinator does not claim Done
- **AND** it either performs a bounded fresh-base retry or integration repair, or reports the exact blocker.

#### Scenario: Two reviewed candidates and main moves before the second finalizes

- **GIVEN** two independent candidates A and B have both passed independent review
- **WHEN** A merges and advances `main` before B is finalized
- **THEN** B is finalized without merging `main` and without developer action
- **AND** the coordinator merges current `main` into B, runs required CI on the merged head and merges B
