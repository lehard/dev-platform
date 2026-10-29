## MODIFIED Requirements

### Requirement: Heavy validation coordinates through an opt-in machine pool

When the machine-local pool configuration named by `DEV_PLATFORM_MACHINE_POOL` is set, every top-level heavy validation run (selected-check execution, the canonical test-group runner and Requirement full-candidate validation) SHALL acquire its weight in tokens from the machine-wide pool before running, SHALL hold them through kernel-released leases inherited by its child processes, and SHALL release them when every holder exits. Nested runs SHALL reuse the parent lease without acquiring more tokens, and the test runner's parallelism SHALL NOT exceed the lease weight. Acquisition SHALL be all-or-nothing and ordered by priority class (`finalize` before `development`) then arrival, SHALL wait while the per-CPU load exceeds the configured limit, available memory is below the configured minimum or, on macOS, the kernel memory pressure level is above normal (an unmeasurable or unknown value SHALL fail explicitly), and SHALL fail explicitly naming the holders after the configured wait timeout instead of running outside the pool. When the variable is unset the run SHALL print `DEV_PLATFORM_MACHINE_POOL: not configured` and run unpooled; a set but missing or invalid configuration SHALL fail explicitly naming the key or path. A selected-check execution SHALL lease one token when every selected command is labelled with a non-test evidence type (`configuration` or `syntax`) and no affected-test precheck runs; otherwise its weight is the test parallelism bounded by the tokens, and an unlabelled command counts as a test command. A waiting run SHALL report the actual blocker first (queue, load, memory, memory pressure, tokens or admission) with its current value and threshold, before the needed and free tokens, its queue position and the holders. A read-only status command SHALL show configuration, holders, waiters, load, memory, the head waiter's blocker in the same terms, and the effective run weight in the caller's environment with how many such runs fit and how many tokens stay idle, warning when the tokens are not a multiple of that weight. The configuration keys and the slot, ticket and lease formats SHALL stay unchanged so that participants on different platform releases share one pool.

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

#### Scenario: Memory pressure blocks admission on macOS

- **GIVEN** a pooled run on macOS whose `vm_stat` available memory is above the minimum
- **WHEN** the kernel memory pressure level is warn or critical
- **THEN** the run waits and its waiting line names memory pressure first with the current level
- **AND** at the normal level the run is admitted
- **AND** an unreadable or unknown level fails explicitly naming the measurement

#### Scenario: Free tokens and a load blocker

- **GIVEN** every token is free and the per-CPU load exceeds the limit
- **WHEN** a run waits
- **THEN** its waiting line and the status name the load with its value and limit first, not a shortage of tokens

#### Scenario: Recommended configuration leaves no idle tokens

- **GIVEN** 6 tokens and a run weight of 3 from `DEV_PLATFORM_TEST_JOBS`
- **WHEN** two heavy runs start
- **THEN** both are admitted together and no token stays free while runs are queued
- **AND** with a weight that does not divide the tokens the status warns and names the idle tokens

#### Scenario: Light selection

- **WHEN** a selected-check execution runs only commands labelled `configuration` or `syntax` and no affected-test precheck
- **THEN** it leases one token
- **AND** a selection with a `test` or unlabelled command leases the test parallelism
