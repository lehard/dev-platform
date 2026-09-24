# agent-workflow Specification Delta

## ADDED Requirements

### Requirement: Explicit Requirement execution reaches terminal delivery

An explicit Execute Requirement request SHALL drive every ready internal child through the existing managed lifecycle and shared integration boundary, stopping only for a consequential decision or external blocker. The supervisor SHALL derive its next action from canonical state rather than persist an independent child queue.

#### Scenario: Ready children are executed in dependency order

- **GIVEN** a Requirement has complete pre-authoring and ready handoffs for sequential children
- **WHEN** execution is requested
- **THEN** each exact child is reused or materialized and bidirectionally linked
- **AND** each child starts or resumes in an isolated managed worktree with only its required predecessor receipt
- **AND** a handoff alone is never reported as terminal delivery

#### Scenario: Parent prose cannot suppress the canonical link

- **GIVEN** an authored child bundle contains `Parent Requirement: owner/repo#N` as prose
- **WHEN** the Requirement handoff is materialized
- **THEN** the generated Issue includes the exact standalone `Requirement: owner/repo#N` backlink before package source evidence is captured
- **AND** the subsequent child start does not require acknowledging an adapter-created source revision

#### Scenario: An interrupted run is resumed

- **GIVEN** a child or shared candidate already exists
- **WHEN** the supervisor repeats Execute Requirement
- **THEN** it derives the current state and resumes the exact child, receipt, candidate or PR without duplication
- **AND** stale or ambiguous evidence blocks the unsafe transition with an actionable diagnostic

#### Scenario: A historical handoff was rebased after delivery

- **GIVEN** a linked child for a handoff's managed change is already canonical or delivered
- **WHEN** pre-authoring refresh changes that handoff's digest
- **THEN** the supervisor reuses the unique exact linked child instead of creating a duplicate Issue
- **AND** multiple children claiming one change fail closed

#### Scenario: A verified ready child stops claiming active writer scope

- **GIVEN** a child has a verified ready receipt at its exact clean committed head
- **WHEN** the supervisor advances to a dependent child
- **THEN** the prior child relinquishes only its own active board writer claim while retaining its worktree, Issue and receipt
- **AND** a dirty worktree, changed head or missing receipt blocks claim release and dependent start

#### Scenario: Terminal completion is authoritative

- **WHEN** all required children have verified ready receipts and one shared candidate has merged through protected publication
- **THEN** the supervisor reconciles child and local main state before reporting the Requirement complete
- **AND** a missing child, failed check, unmerged PR or uncertain external state prevents a Done claim
