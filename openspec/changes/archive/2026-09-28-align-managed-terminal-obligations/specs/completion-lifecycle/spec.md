## MODIFIED Requirements

### Requirement: Unfinished automatic delivery remains explicit completion work

For a platform-owned task configured for automatic PR delivery, an agent SHALL NOT report the task as fully delivered while its exact task PR is still open/pending or while GitHub has merged it but safe local reconciliation remains incomplete. Completion/doctor status SHALL derive that condition from current Git/GitHub state and identify the supported next operation without requiring the human user to remember a Git hand-off. For a managed task, read-only status SHALL distinguish confirmed exact PR merge from full terminal completion. Full completion SHALL be reported only when mandatory post-merge local, Project, linked process-evidence, and required cleanup obligations are fulfilled or have an explicitly supported terminal disposition. Status SHALL derive this from existing authoritative lifecycle and obligation evidence without a second terminal state ledger. A failed or unknown post-merge obligation SHALL be reported as pending or blocking without changing the confirmed merge fact to failure.

#### Scenario: Automatic PR is still waiting remotely

- **GIVEN** local validation and OpenSpec lifecycle work are complete
- **AND** the exact task PR is still open, checking, auto-merge armed, queued, or otherwise pending
- **WHEN** the agent reports task status
- **THEN** it describes delivery as unfinished/recoverable rather than complete
- **AND** identifies normal finish/status as the supported continuation path

#### Scenario: Remote PR merged but local reconciliation remains

- **GIVEN** GitHub reports the exact task PR as `MERGED`
- **AND** local integration/board/worktree reconciliation is still pending
- **WHEN** completion status runs
- **THEN** it reports remote delivery complete but local completion work pending
- **AND** does not ask the human to manually reconstruct publication history

#### Scenario: Publication reaches an actionable blocker

- **WHEN** required checks fail, GitHub authentication/state is unavailable, the exact head changed, or repository policy requires an explicit branch update
- **THEN** the agent may stop automatic delivery
- **AND** reports the specific blocker and preserved remote/local state
- **AND** does not misrepresent the task as successfully delivered

#### Scenario: Historical process evidence blocks finish after merge

- **GIVEN** GitHub confirms the exact task PR is merged and local main and Project reconciliation succeed
- **AND** linked process evidence cannot be resolved
- **WHEN** read-only status is requested
- **THEN** it reports the exact PR as merged, names the pending process-evidence obligation, and does not report full completion
- **AND** finish remains resumable without republishing the PR.

#### Scenario: Explicit disposition of unavailable historical evidence

- **GIVEN** an exact linked historical process Issue is demonstrably unavailable with a definitive 404
- **WHEN** an operator explicitly records a bounded reason through the supported disposition command
- **THEN** the managed source Issue stores an auditable, exact-reference disposition and the command verifies it by read-back
- **AND** status and finish may treat only that reference as disposed while retaining the confirmed merge fact.

#### Scenario: Temporary GitHub failure

- **WHEN** GitHub authentication, permission, transport, or evidence observation is unavailable without definitive proof of historical absence
- **THEN** status reports the relevant obligation as unknown or pending and finish remains resumable
- **AND** no disposition or full completion is inferred.

#### Scenario: Required cleanup remains

- **GIVEN** exact merge and other reconciliation obligations are fulfilled
- **AND** required cleanup is deferred
- **WHEN** read-only status is requested
- **THEN** it reports the cleanup obligation and does not report full completion unless the existing shared cleanup policy classifies it as a terminal warning.
