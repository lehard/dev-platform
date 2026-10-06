## REMOVED Requirements

### Requirement: Completed OpenSpec changes cannot remain active at publication
**Reason**: Archive moves after PR review/repair.
**Migration**: Replaced by "Completed OpenSpec changes cannot remain active at integration".

## ADDED Requirements

### Requirement: Completed OpenSpec changes cannot remain active at integration

For non-trivial OpenSpec work, the platform SHALL treat a change with a completed task checklist as not admissible to integration and not mergeable until the change is archived. A coordinator-managed candidate MAY be published as a PR while its completed change is still active, until review and repair have finished.

#### Scenario: Completed active change blocks finish

- **GIVEN** an active OpenSpec change with one or more task checkboxes
- **AND** every task checkbox is complete
- **WHEN** the candidate is admitted to integration or merged, or a non-coordinator flow publishes it
- **THEN** the flow fails with an instruction to verify and archive the change

#### Scenario: In-progress active change is allowed

- **GIVEN** an active OpenSpec change with at least one incomplete task
- **WHEN** lifecycle hygiene is checked
- **THEN** the change is not treated as stale solely because it is active

### Requirement: Finalization follows review and repair

A coordinator-managed candidate SHALL be archived by a finalize job only after required checks and Independent Review pass for its current task-content identity, using that reused evidence. Finalization SHALL NOT change task-content identity; a later task-content change SHALL return the candidate to review and finalization.

#### Scenario: Review passes
- **WHEN** review and checks pass for the candidate identity
- **THEN** finalize archives the change and the candidate becomes ready
