## MODIFIED Requirements

### Requirement: Permitted actions come from the operator command eligibility

The overview SHALL list as permitted only actions that the existing operator commands (`resume`, `switch-provider`, `reoffer-post-merge`) would accept for the item, computed by the same state, job-kind and claim eligibility function those commands use, and SHALL print the exact command including the PR's current head as `--expected-head`. For a merged PR whose post-merge obligation is exhausted and holds no live claim, it SHALL list `reoffer-post-merge`. For a finding-level escalation, a rejected review, an exhausted round, a disputed disposition, a live claim, a closed PR, a merged PR without an exhausted post-merge obligation, or a needed OpenSpec or business decision, it SHALL list no action and SHALL show the finding or basis and the human decisions available. Where the supported contract cannot apply a decision safely it SHALL say so and SHALL NOT suggest a substitute.

#### Scenario: Operational repair failure
- **GIVEN** a candidate escalated after a failed repair writer
- **WHEN** the overview is shown
- **THEN** `resume` is listed with the exact command and head

#### Scenario: Exhausted repair rounds
- **GIVEN** a candidate escalated for exhausted repair rounds
- **WHEN** the overview is shown
- **THEN** no action is listed and the text names pushing a fix, recording a disposition or closing the PR

#### Scenario: Live claim
- **WHEN** the job holds an unexpired claim
- **THEN** no re-offer is listed and the claim holder and expiry are shown

#### Scenario: Exhausted post-merge obligation
- **GIVEN** a merged PR whose cleanup obligation exhausted its attempts
- **WHEN** the overview is shown or the attention comment is posted
- **THEN** the exact `reoffer-post-merge` command with the merged head is listed, fix the named cause first

#### Scenario: Eligibility agrees with the command
- **WHEN** any candidate state is evaluated
- **THEN** the overview lists an action if and only if the operator command accepts it for that state
