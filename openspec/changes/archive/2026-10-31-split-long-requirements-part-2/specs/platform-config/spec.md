## MODIFIED Requirements

### Requirement: Platform tests one explicit, current-stable Copier version

The platform SHALL record one explicit tested Copier version and SHALL keep every recorded copy of it -- `.dev-platform.toml`, `template/.dev-platform.toml.jinja`, `copier.yml`'s `_min_copier_version`, every CI workflow that installs Copier, and `template/scripts/platform_doctor.py`'s fallback default -- in agreement.

#### Scenario: Tested Copier version is bumped

- **GIVEN** a platform change raises the tested Copier version
- **WHEN** the change is applied
- **THEN** `.dev-platform.toml`, `template/.dev-platform.toml.jinja`, `copier.yml`, every Copier-installing CI workflow, and the doctor's fallback default all reference the same new version
- **AND** regression coverage asserts that agreement so no copy is left stale

#### Scenario: Doctor validates an unconfigured project

- **GIVEN** a downstream project has no explicit `[tools.copier]` table
- **WHEN** the platform doctor checks the installed Copier version
- **THEN** it falls back to the platform's currently tested version, not an earlier one left over from a prior bump

#### Scenario: A new tested version is proven before it is recorded

- **WHEN** a platform change raises the tested Copier version
- **THEN** a render, an update of a project rendered by the previous release, and a rollback check run with the new version before the change is published
- **AND** the evidence names the upstream release source that confirmed the version as stable

### Requirement: Platform configuration is validated once against one schema

`read_platform_config` SHALL validate the project configuration once, at read time, against one platform configuration schema: the keys present in every managed project's rendered configuration are required, and a missing required key or a value of the wrong type SHALL fail with a diagnostic naming the file, the key and the line to add.

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

### Requirement: A removed DeepSeek Harness configuration fails explicitly

Reading a project configuration that still contains `[experimental_runtime.deepseek_harness]` SHALL fail with an error naming the file and stating that the section must be deleted because DeepSeek Harness was removed. The section SHALL NOT be ignored silently.

#### Scenario: Leftover DeepSeek section
- **GIVEN** a `.dev-platform.toml` with `[experimental_runtime.deepseek_harness]`
- **WHEN** the platform configuration is read
- **THEN** it fails naming the file and the section to delete

#### Scenario: No DeepSeek section
- **WHEN** the configuration has no `[experimental_runtime.deepseek_harness]`
- **THEN** it is read as before

#### Scenario: Copier update of a project with the shipped section
- **GIVEN** a project rendered by a release that shipped the DeepSeek section, unchanged
- **WHEN** it is updated with Copier to a release without DeepSeek Harness
- **THEN** the update's bootstrap deletes the shipped section and the shipped DeepSeek files are deleted
- **AND** the configuration reads without error

#### Scenario: Locally modified section
- **WHEN** the section differs from the shipped form
- **THEN** the bootstrap leaves it unchanged and reading the configuration fails naming the section to delete

## ADDED Requirements

### Requirement: Changing the tested Copier version is an explicit confirmed platform change

Changing the tested Copier version SHALL be an explicit platform change, made only after confirming the target version against the primary upstream release source, not adopted merely because a newer number exists or via a prerelease.

#### Scenario: A newer Copier version is published

- **GIVEN** a newer Copier version or prerelease exists
- **WHEN** the tested Copier version would change
- **THEN** the change is an explicit platform change
- **AND** it is made only after confirming the target version against the primary upstream release source

### Requirement: Reading platform configuration fails when the file is absent

`read_platform_config` SHALL fail explicitly when `.dev-platform.toml` is absent.

#### Scenario: Platform configuration file is missing

- **WHEN** `read_platform_config` runs and `.dev-platform.toml` is absent
- **THEN** it fails explicitly

### Requirement: Platform configuration defaults exist only for documented optional keys

Defaults SHALL exist only for documented optional keys defined in the platform configuration schema; the only optional key in the platform configuration schema is `paths.pending_completed_worktree_cleanup`.

#### Scenario: A key without a documented default is absent

- **WHEN** a platform configuration key other than `paths.pending_completed_worktree_cleanup` is absent
- **THEN** no default is supplied for it

### Requirement: Required platform configuration keys are read without substitute defaults

Platform scripts SHALL read required platform configuration keys directly and SHALL NOT supply per-call-site defaults for them, and configuration accessors SHALL NOT substitute values for required platform configuration keys.

#### Scenario: A platform script reads a required key

- **WHEN** a platform script or configuration accessor reads a required platform configuration key
- **THEN** the key is read directly
- **AND** no per-call-site default or substitute value is supplied

### Requirement: Copier update bootstrap deletes only the shipped DeepSeek Harness section

Because Copier never updates `.dev-platform.toml`, the platform bootstrap that a Copier update runs SHALL first delete the exact `[experimental_runtime.deepseek_harness]` section form the platform shipped (with or without its shipped comment) and SHALL leave any other form of that section in place for the reader to reject.

#### Scenario: Shipped section form is present

- **GIVEN** `.dev-platform.toml` contains the exact shipped `[experimental_runtime.deepseek_harness]` section form, with or without its shipped comment
- **WHEN** the platform bootstrap that a Copier update runs executes
- **THEN** it first deletes that section

#### Scenario: Another section form is present

- **GIVEN** `.dev-platform.toml` contains another form of the `[experimental_runtime.deepseek_harness]` section
- **WHEN** the platform bootstrap that a Copier update runs executes
- **THEN** it leaves the section in place for the reader to reject
