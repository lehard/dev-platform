## ADDED Requirements

### Requirement: Heavy validation coordinates through an opt-in machine pool

When the machine-local pool configuration named by `DEV_PLATFORM_MACHINE_POOL` is set, every top-level heavy validation run (selected-check execution, the canonical test-group runner and Requirement full-candidate validation) SHALL acquire its weight in tokens from the machine-wide pool before running, SHALL hold them through kernel-released leases inherited by its child processes, and SHALL release them when every holder exits. Nested runs SHALL reuse the parent lease without acquiring more tokens, and the test runner's parallelism SHALL NOT exceed the lease weight. Acquisition SHALL be all-or-nothing and ordered by priority class (`finalize` before `development`) then arrival, SHALL wait while the per-CPU load exceeds the configured limit or available memory is below the configured minimum (an unmeasurable value SHALL fail explicitly), and SHALL fail explicitly naming the holders after the configured wait timeout instead of running outside the pool. When the variable is unset the run SHALL print `DEV_PLATFORM_MACHINE_POOL: not configured` and run unpooled; a set but missing or invalid configuration SHALL fail explicitly naming the key or path. A read-only status command SHALL show configuration, holders, waiters and load.

#### Scenario: Pool is busy

- **GIVEN** the pool's tokens are held by other live runs
- **WHEN** a heavy validation run starts
- **THEN** it waits, printing who holds the tokens and its queue position
- **AND** it starts only after enough tokens are free, or fails after the wait timeout naming the holders

#### Scenario: Holder dies

- **WHEN** a process holding tokens and all its children exit, including by SIGKILL
- **THEN** its tokens become free without manual cleanup
- **AND** no live holder's tokens are taken

#### Scenario: Finalization waits behind development

- **GIVEN** a `development` run and a `finalize` run both wait
- **WHEN** tokens become free
- **THEN** the `finalize` run is admitted first

#### Scenario: Nested invocation

- **WHEN** a run holding a lease starts selected checks or the test-group runner as a child
- **THEN** the child reuses the lease and acquires no tokens

#### Scenario: Pool not configured or misconfigured

- **WHEN** `DEV_PLATFORM_MACHINE_POOL` is unset
- **THEN** the run prints `DEV_PLATFORM_MACHINE_POOL: not configured` and proceeds unpooled
- **WHEN** it names a missing or invalid configuration
- **THEN** the run fails naming the problem and runs nothing
