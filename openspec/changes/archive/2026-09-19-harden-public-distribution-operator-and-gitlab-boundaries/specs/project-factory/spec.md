## ADDED Requirements

### Requirement: Generic rendered guidance is operator-independent

A Project Factory render with no operator integration enabled SHALL describe a complete portable task/OpenSpec lifecycle without requiring a Development Backlog repository, GitHub Project status mutation, managed fleet registry, process-health labels, or operator credentials.

#### Scenario: External user renders standard GitLab project without operator
- **WHEN** the user selects the standard profile and GitLab provider and leaves operator integration disabled
- **THEN** root agent guidance and linked task-intake/workflow documentation contain no mandatory step that requires Development Backlog or operator-only GitHub state
- **AND** ordinary discuss, quick-task, OpenSpec implementation, verification, branch publication, and human acceptance remain documented and usable.

#### Scenario: Operator integration is enabled
- **WHEN** the user explicitly enables the operator capability during render or configures it by the supported reviewed mechanism
- **THEN** the generated/operator guidance may include Development Backlog, managed status, fleet, and process-health instructions
- **AND** those instructions are clearly scoped to the enabled operator capability rather than presented as universal Dev Platform behavior.

### Requirement: Operator-specific documentation is conditionally rendered or isolated

Project Factory SHALL NOT copy unconditional normative operator instructions into a generic project merely because the public core supports those capabilities. Shared portable guidance MAY link to optional operator documentation only when that documentation does not impose operator behavior on the generic lifecycle.

#### Scenario: Non-operator render is inspected
- **WHEN** the generated repository is searched for normative Development Backlog and managed Project-status instructions
- **THEN** no always-on agent/task lifecycle rule requires those operator actions
- **AND** tests verify the absence in the actual rendered output rather than only in source Jinja variables.
