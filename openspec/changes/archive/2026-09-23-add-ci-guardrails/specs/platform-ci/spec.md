## ADDED Requirements

### Requirement: Central CI catches high-signal Python defects quickly

Central Platform CI SHALL run a locally reproducible, bounded Python static check that detects undefined names and a documented small set of other high-signal errors without requiring whole-codebase type migration or style cleanup.

#### Scenario: Undefined name enters maintained Python source

- **WHEN** a maintained Python module references an undefined name
- **THEN** the local command and central CI fail with a file, line, and rule diagnostic

#### Scenario: Current repository is checked

- **WHEN** the static command checks the existing maintained Python source
- **THEN** it completes within a practical CI budget without unrelated format rewrites
