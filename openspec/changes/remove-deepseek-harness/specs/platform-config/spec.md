## ADDED Requirements

### Requirement: A removed DeepSeek Harness configuration fails explicitly

Reading a project configuration that still contains `[experimental_runtime.deepseek_harness]` SHALL fail with an error naming the file and stating that the section must be deleted because DeepSeek Harness was removed. The section SHALL NOT be ignored silently. Because Copier never updates `.dev-platform.toml`, the platform bootstrap that a Copier update runs SHALL first delete the exact section form the platform shipped (with or without its shipped comment) and SHALL leave any other form in place for the reader to reject.

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
