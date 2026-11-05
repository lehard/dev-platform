## ADDED Requirements

### Requirement: A contribution conflict is detected before required checks

Contribution integration SHALL evaluate review, selected-check and semantic gates, then the conflict of the exact head with the current target head, and only then exact-head required checks. A conflict SHALL move the candidate to integration-repair-pending within the integration-repair budget. Required checks stay mandatory before any merge. A conflict-free head without them SHALL be refused naming the wait.

#### Scenario: A sibling merge conflicts an admitted contribution
- **GIVEN** a contribution in contribution-integration-pending with passed content gates and no required-checks row because its PR is conflicted
- **WHEN** the contribution-integration job runs
- **THEN** the candidate moves to integration-repair-pending naming the conflicting paths, with no manual CI dispatch

#### Scenario: Conflict-free head without required checks
- **WHEN** the head does not conflict with the target and exact-head required checks have not passed
- **THEN** nothing is merged and the refusal names the head and the required-checks wait

#### Scenario: Integration repair budget is spent
- **WHEN** a conflict is found and the integration-repair budget is spent
- **THEN** the candidate is blocked naming the conflict and the budget

### Requirement: An integration repair of a contribution moves its base to the merged target

An integration repair of a contribution SHALL bind the repaired head to the target head it merged as the new contribution base. Equivalent content or a proven target-only merge SHALL keep the content gates, without required checks, and return to contribution-integration-pending. Other changed content SHALL return to review on the new base.

#### Scenario: Clean target merge
- **WHEN** the repaired head is proven to be only the merge of the target into the gated head
- **THEN** the content gates stay, required checks run on the new head, and the identity names the merged target head as contribution base

#### Scenario: Writer resolved a conflict in task content
- **WHEN** the repaired head changes task content relative to the new base
- **THEN** the candidate returns to review, and the review sees only the diff from the new base

### Requirement: Re-admission accepts only a proven contribution base move

Re-admission of a contribution SHALL accept a changed contribution base only when the new base descends from the recorded base and the target contains it. Any other base SHALL be refused naming both bases and `dogfood_task.py reconcile`.

#### Scenario: Reconciled contribution is re-handed off
- **WHEN** a developer re-hands off a contribution whose base moved to a later target head
- **THEN** it is admitted with the moved base and changed content gets a fresh review

#### Scenario: Base outside the target
- **WHEN** the new base is not contained in the target or does not descend from the recorded base
- **THEN** re-admission refuses and writes nothing
