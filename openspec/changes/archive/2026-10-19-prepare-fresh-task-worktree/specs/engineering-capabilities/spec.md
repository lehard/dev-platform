## ADDED Requirements

### Requirement: Task worktree start materializes derived capability surfaces

Creating a multi-agent task worktree SHALL run the capability sync inside the new worktree before the start reports success, so the selected capabilities' gitignored derived provider surfaces exist and the capability audit passes in a fresh worktree without a manual step. If the sync fails, the start SHALL stop with an error naming the worktree, the cause and the repair command, and SHALL leave no registered partial worktree or branch. The platform doctor SHALL remain diagnostic-only and its capability-audit failure SHALL name `python3 scripts/capability_manager.py sync`.

#### Scenario: Fresh task worktree with selected capabilities

- **GIVEN** a project selects one or more capabilities in `dev-platform/capabilities.toml`
- **WHEN** a task worktree is started
- **THEN** each selected capability's derived provider surface exists in the new worktree
- **AND** the capability audit in that worktree passes without running any command by hand

#### Scenario: Sync cannot complete

- **WHEN** the capability sync in the new worktree exits non-zero
- **THEN** the start fails with the worktree path, the sync output and the repair command
- **AND** the new worktree and branch are removed and no board item is registered

#### Scenario: Doctor reports a stale surface

- **WHEN** the doctor's capability audit fails
- **THEN** the failure line names `python3 scripts/capability_manager.py sync`
- **AND** the doctor changes no file
