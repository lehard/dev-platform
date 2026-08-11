## MODIFIED Requirements

### Requirement: Agents own the whole lifecycle

Repository-wide agent instructions SHALL define semantic verify, archive, and configured publication as part of completing non-trivial OpenSpec work so the human user is not expected to remember or relay those steps. For a sealed platform-owned task, doctor and completion status SHALL explicitly identify a recoverable unmerged publication and its safe next operation; an agent SHALL not report delivery complete until automatic publication has merged or an actionable blocking exception is stated explicitly.

#### Scenario: Agent reports completion

- **WHEN** an agent reports a non-trivial OpenSpec task as complete
- **THEN** project checks, semantic verification, archive, and configured publication have already been completed or any blocking exception is stated explicitly

#### Scenario: Sealed automatic publication remains unmerged

- **GIVEN** a platform-owned task has completed required local validation and archive
- **AND** its automatic publication is not merged
- **WHEN** doctor or task completion status runs
- **THEN** it reports an actionable recoverable delivery condition rather than an ordinary inactive-worktree warning
- **AND** it identifies the safe resume/status operation without requiring a human Git hand-off
