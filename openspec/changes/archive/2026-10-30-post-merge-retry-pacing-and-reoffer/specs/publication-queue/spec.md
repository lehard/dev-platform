## ADDED Requirements

### Requirement: Operator re-offers an exhausted post-merge obligation

The coordinator SHALL provide `publication_queue.py reoffer-post-merge --pr N --expected-head H --reason TEXT [--via LABEL]`. It SHALL refuse before any write when the reason or the acting authenticated GitHub identity is missing, the PR is not merged, `H` differs from the merged head, there is no coordinator record at the merged head, no post-merge obligation of the PR is exhausted, or an unexpired claim holds a job of the exhausted obligation. Otherwise it SHALL append one coordinator record at the merged head that keeps state `merged`, task identity and attempt counters, increments `post-merge-reoffers`, and carries a re-offer event naming the obligation kind, reason, actor, `via` label when given, head and time. Eligibility SHALL be one function shared with the lifecycle overview and the attention comment.

#### Scenario: Exhausted cleanup re-offered
- **GIVEN** a merged PR whose cleanup obligation exhausted its attempts
- **WHEN** the operator runs `reoffer-post-merge` with the merged head and a reason
- **THEN** one record is appended with the incremented sequence, actor and reason
- **AND** the cleanup obligation is offered again with a fresh attempt budget

#### Scenario: Refusals before any write
- **WHEN** the PR is open, the expected head differs, nothing is exhausted, or a live claim holds the obligation
- **THEN** the command exits non-zero naming the cause and writes nothing
