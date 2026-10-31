## ADDED Requirements

### Requirement: The friction checkpoint proof ignores declared generated files

The content proof that binds a managed task's friction checkpoint SHALL exclude files declared in `[[generated_files]]` at the merge base of the task and main, so a merge-only reconcile that changes only such files keeps the checkpoint valid. A change to any other task-owned path SHALL still make the checkpoint stale.

#### Scenario: Merge-only reconcile touches only a generated file

- **GIVEN** a recorded friction checkpoint for a managed task
- **WHEN** a reconcile merges main that changed only a declared generated file the task also changed
- **THEN** `agent_friction.py assert-checkpoint` passes without a new checkpoint

#### Scenario: Task content changed after the checkpoint

- **WHEN** a task-owned file other than a declared generated file changes after the checkpoint
- **THEN** `assert-checkpoint` fails naming the checkpoint command
