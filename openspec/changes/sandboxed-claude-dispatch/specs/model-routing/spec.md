## ADDED Requirements

### Requirement: Sandboxed Claude delegation is platform-observed execution

The platform SHALL provide an explicit sandboxed Claude dispatch for a prepared `delegated-child` Claude route. The platform SHALL itself launch a headless Claude writer through the sandboxed writer launch, SHALL open the delegation with `launch_evidence: platform-observed` only after the process started, and SHALL record the execution with mechanism `sandbox-runtime`, an executed participant and platform timing. The terminal routing gate SHALL accept a completed platform-observed sandboxed Claude execution without the detection-only integration postcheck. The native Agent-tool hand-off SHALL remain the default Claude path with its existing self-reported semantics. A pre-launch refusal SHALL record a closed not-launched attempt.

#### Scenario: Sandboxed Claude child completes
- **GIVEN** a prepared standard Claude route with unchanged task content
- **WHEN** the sandboxed Claude dispatch runs and the writer exits successfully with a valid result
- **THEN** the routing record has a closed platform-observed delegation and an execution with `launched: true`, mechanism `sandbox-runtime` and an executed participant
- **AND** the terminal routing gate accepts it

#### Scenario: Native hand-off unchanged
- **WHEN** the supervisor uses the native Agent-tool hand-off
- **THEN** the execution is still recorded as a self-reported claim with no executed participant

#### Scenario: Unsupported platform
- **WHEN** the sandboxed Claude dispatch is requested outside macOS
- **THEN** no process starts, a closed not-launched attempt is recorded and no hard containment is claimed
