## ADDED Requirements

### Requirement: Overview names why an open candidate is idle

For every open, unmerged candidate that has no executing claim, the lifecycle overview SHALL state in plain language what the candidate waits for and who or what moves it next, derived only from the candidate's observable state, offered job, claim, attempt counters and gate evidence. A candidate with an executing claim SHALL report no idle reason. When the reason cannot be established from that state, the overview SHALL report it explicitly as unknown, naming the state, and SHALL NOT present the candidate as healthy or leave it unexplained. The overview SHALL NOT act on the reason.

#### Scenario: Job executed only on the local operator node

- **GIVEN** an open candidate offering an unclaimed `integration-repair` job
- **WHEN** the overview is rendered
- **THEN** it states the candidate waits for that job, which only an operator-run local macOS node executes, and names the operator as the mover

#### Scenario: Waiting for a developer

- **GIVEN** an open PR with no trusted lifecycle record
- **THEN** the overview states it waits for the developer to hand it off

#### Scenario: Waiting for the queue

- **GIVEN** an open candidate in `ready`
- **THEN** the overview states it waits for the publication queue to integrate it

#### Scenario: Attempt limit exhausted

- **GIVEN** an escalated candidate whose repair attempts reached the round limit
- **THEN** the overview states the limit was exhausted and that a human decision is the mover

#### Scenario: Reason cannot be established

- **GIVEN** an open candidate whose state matches no known idle rule
- **THEN** the overview reports "idle reason unknown" with the state, not an empty or healthy indication
