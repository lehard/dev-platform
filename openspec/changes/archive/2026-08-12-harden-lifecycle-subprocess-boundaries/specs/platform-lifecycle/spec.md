## ADDED Requirements

### Requirement: Platform Git failures expose actionable sanitized diagnostics

When a platform-owned Git command is configured to fail on non-zero exit, the lifecycle SHALL surface an actionable bounded error that includes the attempted Git operation, execution directory and exit status together with useful sanitized diagnostic output. It SHALL NOT rely on a raw Python `CalledProcessError` traceback as the primary operator-facing result.

#### Scenario: Git command fails with useful stderr

- **WHEN** a checked Git command exits non-zero and stderr explains a permission, merge, ref or repository blocker
- **THEN** the platform error identifies the command, cwd and exit code
- **AND** includes bounded sanitized stderr sufficient to diagnose the blocker
- **AND** does not require the operator to inspect a Python traceback to discover the captured Git message

#### Scenario: Diagnostic output contains credential-like material

- **WHEN** captured Git output contains credential-like or secret-bearing text
- **THEN** the platform applies existing secret-safety/redaction rules before presenting or persisting the diagnostic
- **AND** does not emit unbounded raw process output

#### Scenario: Caller intentionally uses non-raising Git execution

- **GIVEN** a lifecycle component invokes Git with non-raising semantics to classify return codes itself
- **WHEN** the Git command exits non-zero
- **THEN** the caller still receives the inspectable non-terminal command result
- **AND** the common diagnostic layer does not convert that expected observation into a fatal generic error

#### Scenario: Higher-level resumable state owns the failure

- **WHEN** a structured lifecycle component catches or classifies a Git failure into an existing resumable blocker state
- **THEN** the actionable Git detail may be attached to that state
- **AND** the common wrapper does not erase the higher-level recovery semantics
