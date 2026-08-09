# Completion lifecycle

## ADDED Requirements

### Requirement: Completed OpenSpec changes cannot remain active at publication

For non-trivial OpenSpec work, the platform SHALL treat a change with a completed task checklist as not publishable until the change is archived.

#### Scenario: Completed active change blocks finish

- **GIVEN** an active OpenSpec change with one or more task checkboxes
- **AND** every task checkbox is complete
- **WHEN** the agent runs the platform completion/publication flow
- **THEN** the flow fails with an instruction to verify and archive the change

#### Scenario: In-progress active change is allowed

- **GIVEN** an active OpenSpec change with at least one incomplete task
- **WHEN** lifecycle hygiene is checked
- **THEN** the change is not treated as stale solely because it is active

### Requirement: Archive requires semantic verification evidence

The supported platform archive entrypoint SHALL require a successful semantic OpenSpec verification receipt before archiving a non-trivial change. Agents SHALL prefer `/opsx:verify` when available; environments without that workflow MAY perform the documented equivalent review across completeness, correctness and coherence.

#### Scenario: Verified change archives

- **GIVEN** all implementation tasks are complete
- **AND** `verification.md` records `OpenSpec-Verify: PASS`
- **AND** `verification.md` records a truthful `Verification-Method`
- **AND** strict OpenSpec validation succeeds
- **WHEN** the agent invokes the platform archive entrypoint
- **THEN** OpenSpec archives the change and global strict validation is run

#### Scenario: Missing or failed verification blocks archive

- **GIVEN** a completed change has no PASS verification receipt or no documented verification method
- **WHEN** the agent invokes the platform archive entrypoint
- **THEN** archive is refused without mutating the change

### Requirement: Agents own the whole lifecycle

Repository-wide agent instructions SHALL define `verify -> archive -> publish` as part of completing non-trivial OpenSpec work so the human user is not expected to remember or relay those steps.

#### Scenario: Agent reports completion

- **WHEN** an agent reports a non-trivial OpenSpec task as complete
- **THEN** project checks, semantic verification, archive, and configured publication have already been completed or any blocking exception is stated explicitly
