## ADDED Requirements

### Requirement: Terminal reconciliation resolves a direct managed task's opaque lineage

For a merged managed candidate without BR branch identity, terminal reconciliation SHALL first exit when a trusted successful terminal result for this PR exists. Otherwise it SHALL resolve the archived lineage handle by a page-capped walk of open private Backlog Issues that counts only trusted-author markers, require exactly one verified mapping, then reconcile and close the Issue. Logs and comments SHALL name only the Issue number.

#### Scenario: Direct task without a worktree

- **GIVEN** a merged direct managed task whose worktree was removed
- **WHEN** terminal reconciliation runs
- **THEN** its source Issue is found, verified, set Done and closed

#### Scenario: Unprovable lineage

- **WHEN** no marker, several markers or a marker for another change is found, or the page cap is exceeded
- **THEN** the job stops with a reason and closes nothing

#### Scenario: Repeated job

- **WHEN** a trusted successful terminal result for this PR is already recorded
- **THEN** the job exits without walking the Backlog
