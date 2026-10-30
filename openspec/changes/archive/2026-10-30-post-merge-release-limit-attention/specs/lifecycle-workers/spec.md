## ADDED Requirements

### Requirement: A post-merge job released to the limit raises attention

When the next post-merge job of a merged PR (retrospective, terminal reconciliation or cleanup) has been released after failed runs `MAX_RELEASES` times, derivation SHALL offer no job for it and SHALL report the obligation as exhausted with a reason naming the kind, the release count and the last release cause. The worker run whose release reaches the limit SHALL post the existing post-merge attention on the merged PR, SHALL fail visibly when that post fails, and SHALL NOT publish `blocked-escalation` for the merged PR. The exhausted obligation SHALL be reported by the lifecycle overview and accepted by `reoffer-post-merge`, whose fresh job ids start a fresh release budget. The release escalation of pre-merge jobs SHALL be unchanged.

#### Scenario: Third release of a post-merge job
- **GIVEN** a merged PR whose retrospective job was released twice
- **WHEN** a third run of that job fails and releases its claim
- **THEN** the attention comment is posted on the merged PR with the release count and the last cause
- **AND** derivation offers no job and reports the retrospective as exhausted
- **AND** no `blocked-escalation` record is published

#### Scenario: Below the limit
- **WHEN** the next post-merge job was released fewer than `MAX_RELEASES` times
- **THEN** it is still offered and no attention is posted

#### Scenario: Re-offer after release exhaustion
- **WHEN** the operator re-offers the exhausted obligation with `reoffer-post-merge`
- **THEN** the obligation is offered again under the re-offer's job ids with no releases counted

#### Scenario: Pre-merge job unchanged
- **WHEN** a pre-merge job is released `MAX_RELEASES` times
- **THEN** the candidate moves to `blocked-escalation` as before
