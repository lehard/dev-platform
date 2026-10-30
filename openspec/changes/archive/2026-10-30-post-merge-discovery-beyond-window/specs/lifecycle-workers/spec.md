## ADDED Requirements

### Requirement: Post-merge obligations are discovered beyond the recent-closed window

Lifecycle workers SHALL consider as merged candidates, in addition to the bounded page of most recently updated closed PRs, every closed PR carrying the coordinator's `lifecycle:merged` label that is not labeled `post-merge:settled`, read from a complete paginated listing. A merged PR with an open or exhausted post-merge obligation SHALL be found whatever its position among closed PRs, and the lifecycle overview SHALL consider the same set. If any part of the candidate source cannot be read, the command SHALL fail naming the failed read and SHALL NOT present a truncated set as complete. `work-next` SHALL label a merged candidate `post-merge:settled` only when derivation shows no next post-merge job and no exhausted obligation, SHALL NOT write the label in `--dry-run`, and SHALL fail the run when the label write fails. `work-next --pr N` SHALL read PR N directly rather than selecting it from the listing, so it applies to any merged PR with a lifecycle record.

#### Scenario: Open obligation outside the recent window
- **GIVEN** a coordinator-merged PR with an open post-merge obligation that is not among the 50 most recently updated closed PRs
- **WHEN** `work-next` with post-merge kinds runs, or the lifecycle overview is built
- **THEN** the obligation is offered by the worker and the PR is shown by the overview

#### Scenario: Settled chain stops being re-read
- **WHEN** `work-next` derives a merged PR whose post-merge chain has no next job and no exhausted obligation
- **THEN** it labels the PR `post-merge:settled`
- **AND** later discovery does not read it outside the recent window
- **AND** a PR with an open or exhausted obligation is never labeled

#### Scenario: Dry run writes nothing
- **WHEN** `work-next --dry-run` derives a settled merged PR
- **THEN** no label is written

#### Scenario: Unreadable candidate source
- **WHEN** a page of the open-PR listing, the recent-closed page or the `lifecycle:merged` label listing cannot be read
- **THEN** the command fails naming the read
- **AND** it does not report idle or a partial candidate set

#### Scenario: Selecting one old merged PR
- **WHEN** `work-next --pr N` names a merged PR outside the recent window
- **THEN** PR N is read directly and its post-merge job is offered when one is open
