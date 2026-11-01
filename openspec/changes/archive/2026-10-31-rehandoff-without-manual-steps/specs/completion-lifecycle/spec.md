## MODIFIED Requirements

### Requirement: Developer completion is a handoff at a verified PR

For a coordinator-managed candidate, developer completion SHALL end at a handoff: selected checks and semantic verification evidence for the still-active change, an exact-head PR, a developer friction checkpoint bound to the handoff task content, admission to the coordinator and release of the developer's writer claim. Handoff SHALL NOT wait for review, CI, main movement or merge.

#### Scenario: Developer finishes
- **WHEN** the developer runs finish for a coordinator-managed candidate
- **THEN** the PR exists, the candidate is review-pending and the developer session is free

## ADDED Requirements

### Requirement: Developer handoff enforces the routing gate

Every developer handoff of an active change, first or repeated, through `finish` or `execute_requirement.py advance`, SHALL run the same routing gate as archive before publication and SHALL fail naming the missing routing record or retained execution outcome and its command. An archived re-admission SHALL rely on the gate its first handoff passed.

#### Scenario: First handoff without a retained outcome

- **WHEN** a candidate is handed off without its retained execution outcome
- **THEN** the handoff fails before publication naming the record and its command

### Requirement: A merge-only reconcile keeps the handoff checkpoint

The developer handoff SHALL accept a friction checkpoint whose managed task-content proof is equivalent to the current one, so a reconcile that only merges main needs no new checkpoint. Changed task content SHALL still require a new checkpoint.

#### Scenario: Re-handoff after a merge-only reconcile

- **WHEN** a checkpoint was recorded before a reconcile that changed no task path
- **THEN** the re-handoff accepts it

#### Scenario: Task content changed after the checkpoint

- **WHEN** a task-owned file changed after the checkpoint
- **THEN** the handoff fails naming the checkpoint command
