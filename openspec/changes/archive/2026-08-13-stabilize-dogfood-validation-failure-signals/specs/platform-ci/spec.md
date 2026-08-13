## ADDED Requirements

### Requirement: Concurrent validation tests do not depend on fragile startup timing

Platform-owned concurrency/lock tests SHALL synchronize on explicit readiness where process startup order is part of the assertion and SHALL use bounded deadlines tolerant of normal concurrent test-group scheduling. The test contract SHALL continue to fail a genuinely hung subprocess and SHALL NOT rely on automatic retry to hide timing flakiness.

#### Scenario: Concurrent suite delays a helper process

- **GIVEN** multiple supported test groups run concurrently under normal host contention
- **WHEN** a lock-holder or capability-probe helper starts more slowly than in isolated execution
- **THEN** the test waits for its explicit supported readiness condition within a bounded deadline
- **AND** does not change the semantic test result solely because scheduler latency exceeded an unrealistically short startup assumption

#### Scenario: Helper genuinely hangs

- **WHEN** the controlled helper never reaches its required readiness/completion condition
- **THEN** the bounded deadline expires
- **AND** the test fails with a useful diagnostic
- **AND** no retry loop converts the hang into success
