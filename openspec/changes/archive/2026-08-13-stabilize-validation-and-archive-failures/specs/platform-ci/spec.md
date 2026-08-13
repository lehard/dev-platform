## ADDED Requirements

### Requirement: Supported parallel validation does not change deterministic shared-workspace test outcomes

Test groups that the platform runs concurrently SHALL isolate temporary shared-workspace state sufficiently that scheduler interleaving does not create permission/preflight failures absent from the same scenario in isolation. A group with a proven non-isolatable shared mutable boundary SHALL be serialized explicitly rather than retried.

#### Scenario: Managed-task start tests run under concurrent group load

- **GIVEN** the managed-task/shared-workspace scenarios are valid in isolation
- **WHEN** the supported full test-group runner executes them under representative concurrent load
- **THEN** temporary repository permission/setup state remains valid
- **AND** the semantic result does not change solely because another group is running

#### Scenario: Real shared-workspace permission defect exists

- **WHEN** the controlled fixture contains an actual invalid permission/setgid state
- **THEN** the validation still fails
- **AND** no retry converts that defect to success

### Requirement: Validation failure evidence identifies the failing selected surface

When a selected validation command or test group fails, the lifecycle SHALL expose a bounded sanitized failure descriptor sufficient to identify the selected surface and broad failure class.

#### Scenario: Selected test group fails

- **WHEN** a selected test group exits unsuccessfully
- **THEN** lifecycle evidence identifies that group/check and a bounded failure class
- **AND** automatic friction reporting does not collapse the event to an indistinguishable generic exit status
