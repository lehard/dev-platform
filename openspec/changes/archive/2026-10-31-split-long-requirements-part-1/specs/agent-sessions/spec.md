## MODIFIED Requirements

### Requirement: The platform computes the status of live agent sessions

The platform SHALL maintain, on the operator machine, a registry of agent sessions (Claude Code and Codex) and SHALL compute each session's status itself from hook events: `working`, `idle`, `waiting-input`, `waiting-permission`, `limit-or-error`, `ended` or `unknown`, together with its project, branch, task, root process id and the time of the last event.

#### Scenario: Permission wait is not cleared by another tool
- **GIVEN** a session in `waiting-permission` for tool A
- **WHEN** a PostToolUse event for tool B arrives
- **THEN** the session stays `waiting-permission`
- **AND** it becomes `working` on the PostToolUse of tool A or a new prompt

#### Scenario: Turn cut off by a limit
- **WHEN** a StopFailure event arrives
- **THEN** the session is `limit-or-error` with the error type

#### Scenario: Killed session
- **WHEN** a session ended without SessionEnd and its process is verifiably gone, or its pid now belongs to a process with another start time
- **THEN** it is shown `ended`
- **AND** a failed liveness check never ends a session; liveness is then `unknown`

#### Scenario: Silent session
- **WHEN** a session produced no event for the configured stale time
- **THEN** it is shown `unknown (silent for ...)`, not `working`

## ADDED Requirements

### Requirement: Viewers read agent session status from the registry

Viewers of agent sessions SHALL read the session registry and SHALL NOT compute session status.

#### Scenario: A viewer shows a session's status

- **WHEN** a viewer shows the status of an agent session
- **THEN** it shows the status recorded in the session registry
- **AND** it does not derive the status itself

### Requirement: An undetermined agent session state is unknown

An agent session state that cannot be established SHALL be `unknown` and SHALL NOT be presented as `working`.

#### Scenario: Session state cannot be established

- **WHEN** the registry cannot establish a session's state from its hook events
- **THEN** the session status is `unknown`
- **AND** it is not presented as `working`
