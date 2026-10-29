# agent-sessions Specification

## Purpose
Let the platform know, honestly and from one source, which Claude Code and Codex sessions are alive on the operator machine and what each is doing, so that the lifecycle overview, the coordinator and the board show real activity instead of inferring it from claims.

## Requirements

### Requirement: The platform computes the status of live agent sessions

The platform SHALL maintain, on the operator machine, a registry of agent sessions (Claude Code and Codex) and SHALL compute each session's status itself from hook events: `working`, `idle`, `waiting-input`, `waiting-permission`, `limit-or-error`, `ended` or `unknown`, together with its project, branch, task, root process id and the time of the last event. Viewers SHALL read the registry and SHALL NOT compute status. A state that cannot be established SHALL be `unknown` and SHALL NOT be presented as `working`.

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

### Requirement: Session hooks do not alter the session

Hooks that feed the registry SHALL write nothing to the hook output, SHALL NOT make a permission or stop decision and SHALL NOT use the blocking exit code. An internal failure or an unknown event SHALL be reported on stderr with a non-blocking non-zero exit. Installing the hooks into a settings file SHALL happen only on an explicit command naming that file.

#### Scenario: Registry unwritable
- **WHEN** the hook cannot write the registry
- **THEN** it prints one error line on stderr and exits non-zero without blocking the session

### Requirement: Codex states are limited to what Codex reports

For Codex the platform SHALL record only the turn-complete notification as `idle` and SHALL state that working, waiting and limit states are unavailable, instead of inferring them.

#### Scenario: Codex turn completes
- **WHEN** an `agent-turn-complete` notification arrives
- **THEN** the Codex session is `idle`
