## MODIFIED Requirements

### Requirement: Platform tests do not assert machine speed

A platform test SHALL NOT pass or fail on how fast the host schedules processes. A wait that must not expire SHALL use the shared bounded test deadline; a required order of events SHALL be proven by an observable marker, not by a minimum or maximum elapsed time; a check that a killed process tree is gone SHALL observe the recorded process, not race a fixed sleep. A genuine hang SHALL still fail within the bounded deadline with a diagnostic, and no retry SHALL hide a failure. Repeated runs of the affected tests under artificial CPU oversubscription SHALL show no failures.

#### Scenario: Loaded host delays a child

- **GIVEN** every core is oversubscribed by unrelated CPU-bound processes
- **WHEN** a test's child process starts or streams output later than on an idle host
- **THEN** the test result is unchanged

#### Scenario: Waiting for a lock is proven by order

- **WHEN** a test asserts that a step waited for a lock held by a helper
- **THEN** the proof is that the helper's release marker exists when the serialized step runs, not an elapsed-time bound

#### Scenario: Killed process group is observed

- **WHEN** a test asserts that a process-group kill reached background children
- **THEN** each child recorded its pid before the kill and the test checks those processes are gone within the bounded deadline, instead of racing a short child sleep or bounding the elapsed time

#### Scenario: Genuine hang

- **WHEN** a helper never reaches the event the test waits for
- **THEN** the test fails within the bounded deadline with a diagnostic
