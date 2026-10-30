## ADDED Requirements

### Requirement: A removed DeepSeek Harness configuration fails explicitly

Reading a project configuration that still contains `[experimental_runtime.deepseek_harness]` SHALL fail with an error naming the file and stating that the section must be deleted because DeepSeek Harness was removed. The section SHALL NOT be ignored silently.

#### Scenario: Leftover DeepSeek section
- **GIVEN** a `.dev-platform.toml` with `[experimental_runtime.deepseek_harness]`
- **WHEN** the platform configuration is read
- **THEN** it fails naming the file and the section to delete

#### Scenario: No DeepSeek section
- **WHEN** the configuration has no `[experimental_runtime.deepseek_harness]`
- **THEN** it is read as before
