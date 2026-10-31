## MODIFIED Requirements

### Requirement: The requirement-authoring capability is the single canonical authoring standard

Dev Platform SHALL provide an instruction-only capability `requirement-authoring` whose Markdown is the one canonical source of the Business Requirement authoring standard and its small representative examples, with a descriptor and deterministic eval fixture following the capability lifecycle.

#### Scenario: Project has not enabled the capability

- **WHEN** a managed project renders or updates without enabling `requirement-authoring`
- **THEN** the canonical standard file and the pointers to it are present
- **AND** no provider skill, runtime or project configuration is added solely because of it

#### Scenario: Project enables the capability

- **WHEN** the capability is enabled
- **THEN** Claude and Codex skills contain the same standard content as the canonical file
- **AND** no surface carries a divergent copy of the rules

#### Scenario: Cross-provider verification is not available live

- **WHEN** a live multi-provider behavioral run cannot be performed
- **THEN** the deterministic fixture and rendered-surface identity checks are recorded as the evidence
- **AND** no cross-provider behavior is claimed as verified

### Requirement: Task worktree start materializes derived capability surfaces

Creating a multi-agent task worktree SHALL run the capability sync inside the new worktree before the start reports success, so the selected capabilities' gitignored derived provider surfaces exist and the capability audit passes in a fresh worktree without a manual step.

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

## ADDED Requirements

### Requirement: Process documents reference the canonical requirement-authoring source

Task intake, the ChatGPT Project protocol, agent instructions and the repository map SHALL reference the `requirement-authoring` Markdown rather than restate or fork its rules, so that repository agents, ChatGPT Project and managed downstream projects apply the same standard.

#### Scenario: Process document covers requirement authoring

- **WHEN** task intake, the ChatGPT Project protocol, agent instructions or the repository map address Business Requirement authoring
- **THEN** they reference the `requirement-authoring` Markdown rather than restate or fork its rules
- **AND** repository agents, ChatGPT Project and managed downstream projects apply the same standard

### Requirement: The authoring standard is reachable without enabling the capability

The Business Requirement authoring standard SHALL be reachable through the delivered files without enabling the `requirement-authoring` capability or editing any project file.

#### Scenario: Capability is not enabled

- **WHEN** a project has not enabled the `requirement-authoring` capability
- **THEN** the Business Requirement authoring standard is reachable through the delivered files
- **AND** no project file needs to be edited

### Requirement: Enabling requirement-authoring materializes the native provider skill

Enabling the `requirement-authoring` capability SHALL additionally materialize the same content as the native provider skill.

#### Scenario: Capability is enabled

- **WHEN** a project enables the `requirement-authoring` capability
- **THEN** the same content is additionally materialized as the native provider skill

### Requirement: The requirement-authoring capability creates no runtime state

The `requirement-authoring` capability SHALL NOT create storage, gates, status, approvals, tool runtime or application dependencies.

#### Scenario: Capability is delivered

- **WHEN** the `requirement-authoring` capability is delivered or enabled
- **THEN** it creates no storage, gates, status, approvals, tool runtime or application dependencies

### Requirement: Failed capability sync stops the task worktree start

If the capability sync fails, the multi-agent task worktree start SHALL stop with an error naming the worktree, the cause and the repair command, and SHALL leave no registered partial worktree or branch.

#### Scenario: Capability sync fails

- **WHEN** the capability sync fails while a multi-agent task worktree is created
- **THEN** the start stops with an error naming the worktree, the cause and the repair command
- **AND** no registered partial worktree or branch is left

### Requirement: Platform doctor reports capability-audit failure with the sync command

The platform doctor SHALL remain diagnostic-only and its capability-audit failure SHALL name `python3 scripts/capability_manager.py sync`.

#### Scenario: Doctor finds a capability-audit failure

- **WHEN** the platform doctor finds a capability-audit failure
- **THEN** it reports the failure naming `python3 scripts/capability_manager.py sync`
- **AND** it remains diagnostic-only
