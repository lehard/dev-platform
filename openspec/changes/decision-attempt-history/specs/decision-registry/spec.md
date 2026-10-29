## ADDED Requirements

### Requirement: Repeated attempts and owner choices stay linked to their history

When a Requirement is a second or later attempt at the same problem, it SHALL link the problem's friction root issue, and the delivering change SHALL append to that issue what it did, why the earlier attempts were not enough and what stayed out of scope. An owner choice between options, or a hard-to-reverse decision, SHALL be recorded in the decision registry with its rejected options and revisit triggers, and the change's design SHALL link the record instead of restating the choice. Before authoring a proposal the agent SHALL search for the related root issue and decision records and SHALL link them in the proposal. Specifications SHALL NOT carry this rationale, and decision records SHALL NOT restate requirements.

#### Scenario: Repeated attempt at a known problem

- **GIVEN** a friction root issue and earlier changes for the same problem exist
- **WHEN** a new Requirement addresses that problem
- **THEN** the Requirement links the root issue
- **AND** the delivery appends the change, its effect, why it was not enough and what stayed out of scope to the root issue

#### Scenario: Owner chooses between options

- **WHEN** the owner chooses one of several options or accepts a hard-to-reverse decision
- **THEN** a decision record states the choice, the rejected options and the revisit triggers
- **AND** the change's design links that record

#### Scenario: Proposal authoring

- **WHEN** an agent writes a proposal
- **THEN** it has searched for the related root issue and decision records and links any it found
