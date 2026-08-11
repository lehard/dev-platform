## ADDED Requirements

### Requirement: Protected remote merge revalidates integration checkout safety at the last local mutation boundary

For platform-owned PR publication, immediately before the first ordinary merge, native auto-merge or merge-queue mutation for the exact validated task head, the lifecycle SHALL re-observe the integration checkout under the appropriate integration serialization boundary. Divergent uncommitted integration state SHALL block remote merge intent before GitHub is mutated.

#### Scenario: Integration remains clean after PR checks

- **GIVEN** the exact task PR is ready for a supported protected merge
- **WHEN** the pre-merge integration observation finds no uncommitted state
- **THEN** the existing exact-head merge orchestration may proceed

#### Scenario: Integration becomes dirty while PR waits for checks

- **GIVEN** task start and initial publication preflight observed a clean integration checkout
- **AND** another local actor changes integration while the PR waits remotely
- **WHEN** required checks become ready and finish reaches the merge boundary
- **THEN** the lifecycle observes the new dirty state before merge/auto-merge/queue mutation
- **AND** blocks remote merge intent when that state is divergent

#### Scenario: Divergent integration state is found before merge

- **WHEN** the pre-merge observation finds tracked or untracked local integration content that is not safely reconciled state
- **THEN** publication reports the concrete affected paths and stops before remote merge mutation
- **AND** SHALL NOT automatically stash, reset, clean, delete or overwrite that local state

#### Scenario: Dirty paths merely resemble task paths

- **WHEN** local dirty paths overlap the task diff by name but content equivalence has not been proven
- **THEN** the lifecycle SHALL NOT treat that overlap alone as safe
- **AND** remote merge remains blocked

### Requirement: Pre-merge safety check composes with integration serialization

The last-safe-point observation SHALL not hold the integration lock during long remote check waits, but SHALL acquire/reuse the appropriate serialization before the merge decision and re-observe state after acquiring it.

#### Scenario: Another reconciliation completes before merge decision

- **WHEN** the current task acquires the integration serialization after another task changed local main
- **THEN** it re-fetches/re-observes current local and remote state
- **AND** bases the merge decision on that current state rather than a pre-wait snapshot
