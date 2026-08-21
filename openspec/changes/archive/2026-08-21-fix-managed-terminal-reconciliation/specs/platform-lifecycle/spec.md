## ADDED Requirements

### Requirement: Project-owned managed harnesses reconcile exact terminal delivery

When a reviewed project-owned harness proves that its exact managed PR is
merged, the platform compatibility lifecycle SHALL reconcile only the source
Issue bound by that task's `source_issue + change` provenance to terminal
`Done` and close the Issue as completed. Publish command success alone SHALL
NOT authorize this transition.

#### Scenario: Exact managed PR completes through automatic merge

- **GIVEN** a recognized project harness has an exact managed PR for head A
- **WHEN** GitHub reports that same PR as `MERGED` with `headRefOid` A
- **THEN** only the provenance-bound source Issue is reconciled to `Done` and closed
- **AND** a different archived or integration task identity is not mutated

#### Scenario: Terminal mutation fails after confirmed merge

- **GIVEN** GitHub confirms the exact managed PR is merged
- **WHEN** Project or Issue terminal mutation fails
- **THEN** the lifecycle reports pending terminal reconciliation and does not claim completion
- **AND** a later finish retry performs only the remaining reconciliation after re-proving the exact merge

#### Scenario: Delayed required checks do not change recovery semantics

- **GIVEN** a recognized project harness has just published an exact PR
- **WHEN** required checks are not yet registered for its expected head
- **THEN** the lifecycle remains resumable and does not set `Done`
- **AND** after exact merge it uses the same terminal reconciliation path
