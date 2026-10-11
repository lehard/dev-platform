## MODIFIED Requirements

### Requirement: New work reconciles an authoritative pending platform rollout first

Before a supported new task starts in a managed repository, the platform SHALL determine whether the repository has an authoritative eligible Dev Platform rollout PR that still needs adoption. For platform-owned task execution, this reconciliation SHALL occur before creating a new task branch or worktree. A safely adoptable rollout SHALL be merged and locally reconciled before product work starts; an unsafe or ambiguous rollout SHALL block new work with an actionable state.

A session MAY explicitly defer rollout adoption with `DEV_PLATFORM_DEFER_ROLLOUT=1`, which the `--defer-rollout` flag of `start_task.py`, `start_managed_task.py`, `execute_managed_task.py` and `execute_requirement.py advance` sets for the process and its children. While the deferral is set, task start SHALL only observe the rollout: it SHALL NOT merge, close, relabel or otherwise change the rollout PR, SHALL NOT synchronize local integration for it, and SHALL report that the rollout was skipped, naming the PR and the deferral. Any other non-empty value of the variable SHALL be an explicit error naming it. Without the deferral, immediately before merging a rollout, start SHALL announce the PR, the merge and the local synchronization it is about to perform and how to defer them, and `agent_doctor.py` SHALL report a green pending rollout as one the next task start will merge.

#### Scenario: No pending rollout exists

- **WHEN** pre-task reconciliation finds no authoritative eligible rollout PR for the repository
- **THEN** normal task synchronization/start continues without a rollout-specific human step

#### Scenario: Current rollout is green and safe to adopt

- **GIVEN** pre-task reconciliation finds the current authoritative eligible rollout PR
- **AND** the exact current PR head satisfies required downstream GitHub gates and merge policy
- **AND** no rollout deferral is set for the session
- **WHEN** the supported task start proceeds
- **THEN** start announces the rollout merge and local synchronization it is about to perform
- **AND** the platform merges that exact rollout through ordinary non-bypass GitHub policy
- **AND** confirms the remote merge
- **AND** synchronizes the local integration branch to the merged remote state
- **AND** only then creates or enters the new task workspace

#### Scenario: Rollout checks or policy are not satisfied

- **GIVEN** an authoritative pending rollout exists
- **AND** no rollout deferral is set for the session
- **WHEN** its required checks are pending/failed, it conflicts, its head changes, required review remains unsatisfied, or another safety condition prevents ordinary merge
- **THEN** the platform does not start new product work on top of the older platform state
- **AND** reports a concrete pending/blocker state that can be retried after the condition changes
- **AND** does not force-push or bypass repository protection

#### Scenario: Rollout merged before local reconciliation completed

- **GIVEN** the authoritative rollout PR is already confirmed merged remotely
- **AND** local integration is still behind
- **AND** no rollout deferral is set for the session
- **WHEN** pre-task reconciliation is retried
- **THEN** the platform synchronizes local integration idempotently
- **AND** does not create or merge a second rollout PR

#### Scenario: Session defers a green pending rollout

- **GIVEN** an authoritative pending rollout PR is green and safe to adopt
- **AND** the session set `DEV_PLATFORM_DEFER_ROLLOUT=1` (directly or through `--defer-rollout`)
- **WHEN** a managed or quick task starts
- **THEN** the rollout PR remains open and unchanged and local integration is not synchronized for it
- **AND** start reports that the rollout was skipped, naming the PR and the session deferral
- **AND** start completes normally on the current platform state

#### Scenario: Session defers a pending rollout that is not green

- **GIVEN** an authoritative pending rollout PR whose checks are pending, failed or ambiguous
- **AND** the session set `DEV_PLATFORM_DEFER_ROLLOUT=1`
- **WHEN** a task starts
- **THEN** start reports the rollout as skipped with its observed state instead of blocking, and changes nothing

#### Scenario: Deferral set but nothing is pending

- **GIVEN** `DEV_PLATFORM_DEFER_ROLLOUT=1` and no authoritative pending rollout
- **WHEN** a task starts
- **THEN** start proceeds as it does without the deferral

#### Scenario: Invalid deferral value

- **WHEN** `DEV_PLATFORM_DEFER_ROLLOUT` is set to a value other than empty or `1`
- **THEN** start fails before any rollout observation or mutation, naming the variable and the accepted value

#### Scenario: Deferral does not affect project-owned harnesses

- **GIVEN** a repository uses `harness_mode=project`
- **WHEN** a task starts with or without the deferral
- **THEN** platform reconciliation is skipped exactly as before
