## ADDED Requirements

### Requirement: Concurrent lifecycle tests synchronize observable readiness

Lifecycle tests SHALL establish the process state required by an assertion through a bounded readiness handshake rather than assuming it exists after a fixed sleep.

#### Scenario: Child startup is delayed

- **WHEN** host scheduling delays a test child before it publishes its descendant identity
- **THEN** the fixture waits within a bounded readiness deadline
- **AND** cleanup timeout measurement starts only after readiness is proven

#### Scenario: Child never becomes ready

- **WHEN** the readiness deadline expires
- **THEN** the test fails with process and retained-output diagnostics

### Requirement: Default test concurrency is bounded and overridable

The canonical test-group runner SHALL use a conservative upper bound for automatically selected parallelism and SHALL retain an explicit operator override.

#### Scenario: Host exposes many CPUs

- **WHEN** no explicit test-job count is configured
- **THEN** the runner does not start an unbounded CPU-derived number of concurrent groups

#### Scenario: Operator selects a job count

- **WHEN** `DEV_PLATFORM_TEST_JOBS` or the supported CLI option supplies a valid value
- **THEN** the explicit value is used and recorded in test evidence

### Requirement: Publication recovery timeouts remain bounded and diagnostic

Publication recovery tests SHALL use one configurable bounded timeout and SHALL not hide a timeout through automatic reruns.

#### Scenario: Recovery helper exceeds its deadline

- **WHEN** a recovery helper does not complete within the configured test deadline
- **THEN** the test fails with its process identity, state and retained output
