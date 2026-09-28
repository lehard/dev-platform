# platform-ci Specification Delta

## MODIFIED Requirements

### Requirement: Publication recovery timeouts remain bounded and diagnostic

Publication recovery tests SHALL use one configurable bounded timeout and SHALL not hide a timeout through automatic reruns. A test that asserts retained partial output from a deliberately hung recovery helper SHALL establish that output's readiness before starting its short timeout measurement.

#### Scenario: Recovery helper exceeds its deadline

- **GIVEN** a recovery helper has flushed its expected partial output and signalled readiness within a bounded startup window
- **WHEN** the helper does not complete within the configured test deadline
- **THEN** the test fails with its process identity, state and retained output
- **AND** the timeout is measured only after readiness is proven

#### Scenario: Recovery helper startup is delayed by parallel load

- **WHEN** parallel scheduling delays the helper before it emits its expected partial output
- **THEN** the test waits for bounded readiness before starting the short hung-helper deadline
- **AND** it does not retry the timeout assertion or increase the global test deadline
