## ADDED Requirements

### Requirement: Operators re-offer review and repair jobs on another provider

The coordinator SHALL provide a supported operator command that re-offers an open candidate's review or repair job on an explicit ordered list of supported providers. It SHALL append one head-bound record that preserves task identity, gates, findings and every attempt counter, offers the job as a distinct re-offer of the same attempt, and records the previous and new providers, the reason and the time. It SHALL spend no retry or repair round and SHALL NOT require closing the PR or a new developer handoff. It SHALL refuse a candidate whose job holds an unexpired claim, a state that is not an unfinished review or repair, a merged or closed PR, and an unsupported or duplicated provider. Offering the providers already offered SHALL change nothing. Later retries, repair and review jobs of the candidate SHALL follow the new providers.

#### Scenario: Switch an open candidate
- **GIVEN** a review-pending candidate whose job names codex and has no live claim
- **WHEN** the operator switches it to claude with a reason
- **THEN** the candidate remains review-pending with its gates and attempts unchanged
- **AND** its job names claude and records codex as the previous provider and the reason
- **AND** the former job is no longer the candidate's job

#### Scenario: Switch under a live claim
- **WHEN** the operator switches a candidate whose job has an unexpired claim
- **THEN** the command refuses naming the claim and nothing is published

#### Scenario: Repair keeps its findings
- **WHEN** a repair-pending candidate is switched
- **THEN** the repair job still receives the candidate's findings

### Requirement: Operational escalation has a supported exit

The coordinator SHALL provide a supported operator command that resumes a blocked-retryable review or repair candidate without an automatic job, and a blocked-escalation candidate whose escalation is an operational repair outcome (worker failure, harness rejection or no change), after a human decision. The command SHALL require a reason, SHALL accept a provider list, SHALL restore the findings-bearing red gate from the failed review or required-checks gate, and SHALL re-offer the same round without spending budget. It SHALL refuse finding-level escalation (proposed rejection, exhausted rounds, rejected review), malformed records and closed PRs with a message naming the human actions available. A candidate escalated before its providers were recorded SHALL require an explicit provider.

#### Scenario: Repair worker failed
- **GIVEN** a candidate escalated after a failed repair writer
- **WHEN** the operator resumes it with a reason
- **THEN** it returns to repair-pending on the same round with its findings

#### Scenario: Exhausted rounds
- **WHEN** the operator resumes a candidate escalated for exhausted repair rounds
- **THEN** the command refuses and names pushing a fix, recording a disposition or closing the PR
