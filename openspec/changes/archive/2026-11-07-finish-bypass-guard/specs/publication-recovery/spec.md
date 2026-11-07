## ADDED Requirements

### Requirement: Finish leaves a trace bound to the published head

When `delivery_trace = true` is set in `[settings]` of the check configuration, publication SHALL, after every `finish` gate and before reading the head it publishes, make the head carry exactly one `Dev-Platform-Finish` trailer whose value is the tree of the head commit, through an empty commit with the subject of the previous head unless the head is already valid.

#### Scenario: First publication

- **GIVEN** the setting is enabled and all `finish` gates passed
- **WHEN** publication starts
- **THEN** the head gains an empty commit with a valid trace and an unchanged subject
- **AND** the push, the PR lookup and `--match-head-commit` use that head

#### Scenario: Finish repeats on a traced head

- **GIVEN** the head already carries a valid trace
- **WHEN** `finish` runs again
- **THEN** no commit is added
- **AND** the recorded checkpoint, check evidence and review stay valid, because they bind task content

#### Scenario: Project without the setting

- **GIVEN** the check configuration has no `delivery_trace` setting
- **WHEN** publication runs
- **THEN** no commit is added

#### Scenario: Setting is not a boolean

- **GIVEN** `delivery_trace` is not a boolean
- **WHEN** publication runs
- **THEN** it stops naming the setting

### Requirement: Reconcile keeps the trace of a traced pull request

`reconcile` SHALL add a valid trace to its merged head before pushing it to a published PR only when the published head carried a valid trace. A local descendant that `reconcile` pushes SHALL get no trace, because `finish` has not checked its content.

#### Scenario: Traced PR is reconciled

- **GIVEN** the published head carries a valid trace
- **WHEN** `reconcile` merges main and pushes
- **THEN** the pushed head carries a valid trace

#### Scenario: PR without a trace is reconciled

- **GIVEN** the published head carries no valid trace
- **WHEN** `reconcile` merges main and pushes
- **THEN** the pushed head carries no trace
