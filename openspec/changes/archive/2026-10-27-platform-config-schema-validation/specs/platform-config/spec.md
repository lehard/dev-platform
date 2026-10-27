## ADDED Requirements

### Requirement: Platform configuration is validated once against one schema

`read_platform_config` SHALL fail explicitly when `.dev-platform.toml` is absent. It SHALL validate the project configuration once, at read time, against one platform configuration schema: the keys present in every managed project's rendered configuration are required, and a missing required key or a value of the wrong type SHALL fail with a diagnostic naming the file, the key and the line to add. Defaults SHALL exist only for documented optional keys defined in that schema; the only optional key in this schema is `paths.pending_completed_worktree_cleanup`. Platform scripts SHALL read required keys directly and SHALL NOT supply per-call-site defaults for them, and configuration accessors SHALL NOT substitute values for required keys.

#### Scenario: Configuration file is absent

- **GIVEN** a checkout without `.dev-platform.toml`
- **WHEN** a platform script reads the platform configuration
- **THEN** it fails naming the missing file instead of using built-in values

#### Scenario: Required key is missing

- **GIVEN** `.dev-platform.toml` has no `main_branch`
- **WHEN** the platform configuration is read
- **THEN** it fails naming `main_branch`, the file and the line to add

#### Scenario: Required key has the wrong type

- **GIVEN** `.dev-platform.toml` sets `protected_main = "yes"`
- **WHEN** the platform configuration is read
- **THEN** it fails naming `protected_main` and the expected boolean type

#### Scenario: Optional key is absent

- **GIVEN** a complete configuration without `paths.pending_completed_worktree_cleanup`
- **WHEN** the platform configuration is read
- **THEN** the schema default `.claude/pending-completed-worktree-cleanup.json` is used
