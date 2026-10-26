## RENAMED Requirements

- FROM: `### Requirement: Portable finish reuses archive check evidence for the exact validated tree`
- TO: `### Requirement: Finish reuses check evidence for unchanged task content`

## MODIFIED Requirements

### Requirement: Finish reuses check evidence for unchanged task content

`finish` SHALL NOT execute the selected local checks again when recorded selected-check evidence proves that the task content being published passed the checks finish requires. One rule SHALL decide for managed and quick tasks in the `portable` and `coordinator` lifecycles: the evidence outcome is success, the current required selection is ready and every one of its commands was executed successfully by the evidence, and the evidence's task-content proof is equivalent to the current one — equal task-content digest and scope, and when the bases differ, the recorded base is an ancestor of the current base and no task path changed between them. A clean merge or rebase on an advanced `main` that changed no task path SHALL therefore keep the evidence reusable. Reuse SHALL NOT relax the freshness gate that decides whether a head may publish. Finish SHALL print whether the evidence was reused or why it was not, and SHALL run the required validation when reuse is not proven. A managed task's evidence SHALL be its change's `automated-checks.json`; unreadable, failed or mismatched managed evidence SHALL continue to stop publication. A quick task's evidence SHALL be recorded machine-locally in its worktree's git directory on explicit request, never in the tree, with a quick-task content proof of its own diff from the merge base with the remote main excluding declared generated files; finish SHALL request it when it runs a quick task's checks, and an absent record SHALL be a named reason to run the checks. Required CI on the exact pull request head SHALL remain the merge gate.

#### Scenario: Unchanged archived content

- **GIVEN** a managed task in a `portable` project whose archive executed the selected checks successfully and wrote version-2 evidence
- **AND** only the archive materialization and lifecycle evidence changed afterwards and main did not advance
- **WHEN** finish runs
- **THEN** finish prints that the archive evidence was reused
- **AND** the selected checks are executed once over archive and finish

#### Scenario: Clean rebase with an unchanged own diff

- **GIVEN** a managed or quick task whose recorded evidence passed
- **AND** main advanced without touching any task path and the task merged it cleanly
- **WHEN** finish runs in the `portable` or `coordinator` lifecycle
- **THEN** finish prints that the evidence was reused and does not execute the selected checks
- **AND** the coordinator developer handoff accepts the same evidence

#### Scenario: Task content changed after archive

- **WHEN** a source or test path of a managed task changes after its validation
- **THEN** the existing evidence gate stops publication, naming the stale evidence
- **AND** for a quick task finish prints that the task content differs and executes the required checks

#### Scenario: Base changed after archive

- **GIVEN** main advanced after archive by changing a path the task also changes and the task branch was reconciled with it
- **WHEN** finish runs
- **THEN** for a managed task the existing evidence gate stops publication, naming the stale evidence
- **AND** for a quick task finish prints that the evidence is not reusable because main changed a task path and executes the required checks

#### Scenario: Required selection not covered

- **WHEN** the selection finish requires now contains a command that the evidence does not show as executed successfully
- **THEN** finish prints the uncovered command as the reason and executes the required checks

#### Scenario: Quick task without recorded evidence

- **GIVEN** a quick task with no machine-local evidence record
- **WHEN** finish runs
- **THEN** finish prints that no quick-task evidence is recorded, executes the required checks and records evidence for the next finish

#### Scenario: Coordinator lifecycle unchanged

- **WHEN** finish runs for a coordinator-managed candidate
- **THEN** finish runs no checks and the developer handoff accepts the evidence by the same task-content proof as before
