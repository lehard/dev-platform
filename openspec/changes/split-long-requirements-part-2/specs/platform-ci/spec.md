## MODIFIED Requirements

### Requirement: Release candidates prove installed harness compatibility

Central platform CI and release publication SHALL run the same bounded installation validation before an immutable release is created.

#### Scenario: Release candidate has invalid generated whitespace

- **WHEN** an installed or upgraded candidate contains a diff hygiene failure
- **THEN** release installation validation fails before an immutable tag is published

#### Scenario: Required configuration or capability surface is missing

- **WHEN** a supported installation lacks a required rendered input or a selected capability surface
- **THEN** release installation validation fails before publication

#### Scenario: Harness ownership differs

- **WHEN** both supported GitHub harness ownership modes are validated
- **THEN** each mode receives platform-owned installation checks
- **AND** neither mode executes downstream product/application tests

### Requirement: Test groups are independent of module order and substitution

Platform test modules SHALL register platform modules in `sys.modules` only through one shared loader that reuses the instance already registered for the same file, and SHALL scope any temporary stand-in with patching that restores `sys.modules`, so that code under test and every test in a process share one instance per registered module name. A test MAY load a file under a distinct private alias name that production code never imports.

#### Scenario: Group runs in isolation and in its group
- **GIVEN** a canonical test group containing modules that previously replaced platform modules at import time
- **WHEN** the group runs alone and as part of its configured group order
- **THEN** both runs produce the same result

#### Scenario: A test substitutes a module instance
- **WHEN** a test module assigns a platform module into `sys.modules` directly, or holds an instance different from the registered one
- **THEN** the guard fails naming the test file and the offending line or duplicated module

### Requirement: Platform tests do not assert machine speed

A platform test SHALL NOT pass or fail on how fast the host schedules processes.

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

### Requirement: Developer validation compiles the code on the CI Python version

The full local check set SHALL include a repository-owned step that reads the Python version pinned by the CI validation workflow.

#### Scenario: Compile error only on the CI version
- **GIVEN** local checks run on Python 3.13 and CI pins Python 3.11
- **WHEN** a source compiles on 3.13 but not on 3.11
- **THEN** the step fails naming both versions and the compile error

#### Scenario: CI-version interpreter is missing
- **GIVEN** local checks run on a minor version other than the CI version
- **WHEN** no interpreter of the CI version is on PATH
- **THEN** the step refuses naming both versions and does not pass

#### Scenario: Matching versions
- **GIVEN** the local interpreter has the CI minor version
- **WHEN** the step runs
- **THEN** it reports the match and passes without a second compilation

## ADDED Requirements

### Requirement: Release installation validation uses real Copier installation and upgrade

The bounded installation validation run by central platform CI and release publication SHALL use real Copier fresh installation and upgrade of representative officially supported configurations, including both GitHub harness ownership modes and the documented alternative SCM scope.

#### Scenario: Supported configurations are installed and upgraded

- **WHEN** central platform CI or release publication runs the bounded installation validation
- **THEN** representative officially supported configurations are freshly installed and upgraded with real Copier
- **AND** the configurations include both GitHub harness ownership modes and the documented alternative SCM scope

### Requirement: Release installation validation applies rollout-equivalent integrity checks

The bounded installation validation run by central platform CI and release publication SHALL apply rollout-equivalent platform-owned hygiene and integrity checks to the resulting installations, including reject detection, diff hygiene, rendered platform doctor, and required platform surfaces.

#### Scenario: Installations are checked

- **WHEN** the bounded installation validation has produced installations
- **THEN** rollout-equivalent platform-owned hygiene and integrity checks run on them
- **AND** the checks include reject detection, diff hygiene, rendered platform doctor, and required platform surfaces

### Requirement: Release installation validation runs no downstream tests

The bounded installation validation run by central platform CI and release publication SHALL NOT run downstream product or application tests.

#### Scenario: Validation scope is applied

- **WHEN** the bounded installation validation runs
- **THEN** it does not run downstream product or application tests

### Requirement: A canonical test group gives the same result alone and in its group

A selected canonical test group SHALL produce the same result when run in isolation and inside its group.

#### Scenario: Group is run two ways

- **WHEN** a selected canonical test group is run in isolation and inside its group
- **THEN** both runs produce the same result

### Requirement: A guard rejects platform module registration outside the shared loader

The platform SHALL include an automated guard that fails when a test registers a platform module outside the one shared loader through which platform test modules register platform modules in `sys.modules`, or when, after importing test modules in forward or reverse order, a test holds a platform module that differs from the registered instance of the same name.

#### Scenario: A test bypasses the shared loader or holds a different instance

- **WHEN** a test registers a platform module outside the shared loader, or holds a platform module that differs from the registered instance of the same name after test modules are imported in forward or reverse order
- **THEN** the automated guard fails

### Requirement: Platform test waits use the shared bounded deadline

In a platform test, a wait that must not expire SHALL use the shared bounded test deadline.

#### Scenario: Test waits for an event

- **WHEN** a platform test performs a wait that must not expire
- **THEN** the wait uses the shared bounded test deadline

### Requirement: Platform test event order is proven by an observable marker

In a platform test, a required order of events SHALL be proven by an observable marker, not by a minimum or maximum elapsed time.

#### Scenario: Test asserts an order of events

- **WHEN** a platform test asserts a required order of events
- **THEN** the order is proven by an observable marker
- **AND** not by a minimum or maximum elapsed time

### Requirement: Platform test process-tree checks observe the recorded process

In a platform test, a check that a killed process tree is gone SHALL observe the recorded process, not race a fixed sleep.

#### Scenario: Test checks a killed process tree

- **WHEN** a platform test checks that a killed process tree is gone
- **THEN** it observes the recorded process
- **AND** it does not race a fixed sleep

### Requirement: A genuine platform test hang fails within the bounded deadline

A genuine hang in a platform test SHALL still fail within the shared bounded test deadline with a diagnostic.

#### Scenario: Platform test hangs

- **WHEN** a platform test genuinely hangs
- **THEN** it fails within the shared bounded test deadline with a diagnostic

### Requirement: No retry hides a platform test failure

No retry SHALL hide a platform test failure.

#### Scenario: Platform test fails

- **WHEN** a platform test fails
- **THEN** no retry hides the failure

### Requirement: Speed-independent platform tests pass under CPU oversubscription

Repeated runs of the affected platform tests under artificial CPU oversubscription SHALL show no failures.

#### Scenario: Affected tests run under oversubscription

- **WHEN** the affected platform tests are run repeatedly under artificial CPU oversubscription
- **THEN** no run fails

### Requirement: The CI Python compile step compiles on a minor version mismatch

When the interpreter running the local checks has a different minor version than the Python version pinned by the CI validation workflow, the repository-owned step of the full local check set that reads the Python version pinned by the CI validation workflow SHALL compile the repository's Python sources with an interpreter of the CI version and SHALL fail when compilation fails.

#### Scenario: Local interpreter has another minor version

- **GIVEN** the interpreter running the local checks has a different minor version than the CI-pinned Python version
- **WHEN** the step that reads the CI-pinned Python version runs
- **THEN** it compiles the repository's Python sources with an interpreter of the CI version
- **AND** it fails when compilation fails

### Requirement: The CI Python compile step refuses without the CI version

When the CI version cannot be read, no interpreter of that version is available, or the available interpreter reports another version, the repository-owned step of the full local check set that reads the Python version pinned by the CI validation workflow SHALL refuse explicitly naming both versions, without substituting a version or interpreter.

#### Scenario: CI version interpreter cannot be used

- **WHEN** the CI Python version cannot be read, no interpreter of that version is available, or the available interpreter reports another version
- **THEN** the step that reads the CI-pinned Python version refuses explicitly naming both versions
- **AND** it does not substitute a version or interpreter

### Requirement: The CI Python compile step detects only compile-time errors

The repository-owned step of the full local check set that reads the Python version pinned by the CI validation workflow SHALL detect only compile-time errors; runtime behaviour differences between Python versions are outside its scope and remain covered by required CI.

#### Scenario: A runtime-only difference exists between versions

- **WHEN** a source behaves differently at runtime on the CI Python version but compiles
- **THEN** the step that reads the CI-pinned Python version does not report it
- **AND** the difference remains covered by required CI
