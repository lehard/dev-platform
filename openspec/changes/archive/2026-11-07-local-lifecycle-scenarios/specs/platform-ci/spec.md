## ADDED Requirements

### Requirement: Simple-path lifecycle breakages are pinned by local Git tests

The repository test suite SHALL contain regression tests that run on local Git only, with no network, sandbox or GitHub CLI, for lifecycle breakages that already happened on the simple delivery path and that no other test catches. Each such test SHALL name its source breakage.

#### Scenario: Reconcile conflict with a declared generated file

- **GIVEN** a quick task and main that both change a tracked file and a declared generated file
- **WHEN** `finish_task.py --reconcile` stops at the conflict and every printed step is followed literally
- **THEN** the merge is committed, the generated file is regenerated, the task commit stays in history and the final reconcile is a no-op
- **AND** while the merge is unfinished, `--status` exits without a traceback naming reconcile, and a repeated reconcile prints the same steps

#### Scenario: Test file without a group

- **GIVEN** the preflight commands this repository configures
- **WHEN** the cheap project gates run on a tree with a test file that belongs to no group
- **THEN** they are refused naming that file
- **AND** they pass once the file belongs to a group
