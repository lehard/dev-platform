## MODIFIED Requirements

### Requirement: Consequential decisions have a durable runtime-independent history

Dev Platform SHALL maintain a version-controlled repository decision registry that supported agent surfaces can discover without provider memory.

#### Scenario: Decision is reconsidered

- **GIVEN** an existing decision has new evidence or its revisit trigger fires
- **WHEN** the conclusion changes
- **THEN** a new record links and supersedes the earlier record
- **AND** the earlier rationale and evidence remain readable

### Requirement: Repeated attempts and owner choices stay linked to their history

When a Requirement is a second or later attempt at the same problem, it SHALL link the problem's friction root issue.

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

## ADDED Requirements

### Requirement: Consequential decision records state their full decision context

A consequential record SHALL state its stable identity, scope, decision date and revision, accepted/current choice, rejected-for-now and deferred/watch alternatives where applicable, rationale, evidence links, revisit triggers, and supersession relationship.

#### Scenario: Consequential decision is recorded

- **WHEN** a consequential decision is recorded
- **THEN** the record states its stable identity, scope, decision date and revision and accepted/current choice
- **AND** it states rejected-for-now and deferred/watch alternatives where applicable, rationale, evidence links, revisit triggers, and supersession relationship

### Requirement: A changed decision is recorded as a new linked decision

A later change SHALL create a new decision that links the earlier record and preserves the earlier rationale and evidence.

#### Scenario: Decision changes later

- **WHEN** a recorded decision changes later
- **THEN** a new decision is created that links the earlier record
- **AND** the earlier rationale and evidence are preserved

### Requirement: Delivering change appends its attempt to the friction root issue

When a Requirement is a second or later attempt at the same problem, the delivering change SHALL append to the problem's friction root issue what it did, why the earlier attempts were not enough and what stayed out of scope.

#### Scenario: Repeated attempt is delivered

- **WHEN** a change delivers a Requirement that is a second or later attempt at the same problem
- **THEN** the change appends to the problem's friction root issue what it did, why the earlier attempts were not enough and what stayed out of scope

### Requirement: Owner choices are recorded in the decision registry and linked from the design

An owner choice between options, or a hard-to-reverse decision, SHALL be recorded in the decision registry with its rejected options and revisit triggers, and the change's design SHALL link the record instead of restating the choice.

#### Scenario: Owner choice or hard-to-reverse decision

- **WHEN** an owner chooses between options or a hard-to-reverse decision is made
- **THEN** it is recorded in the decision registry with its rejected options and revisit triggers
- **AND** the change's design links the record instead of restating the choice

### Requirement: Proposal authoring searches for and links related history

Before authoring a proposal the agent SHALL search for the related root issue and decision records and SHALL link them in the proposal.

#### Scenario: Agent authors a proposal

- **WHEN** the agent is about to author a proposal
- **THEN** it searches for the related root issue and decision records
- **AND** it links them in the proposal

### Requirement: Specifications and decision records keep separate content

Specifications SHALL NOT carry repeated-attempt and owner-choice rationale, and decision records SHALL NOT restate requirements.

#### Scenario: Rationale and requirements are written

- **WHEN** repeated-attempt or owner-choice rationale and requirements are written
- **THEN** specifications do not carry that rationale
- **AND** decision records do not restate requirements
