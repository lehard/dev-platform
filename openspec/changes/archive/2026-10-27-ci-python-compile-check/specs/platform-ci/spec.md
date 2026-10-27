## ADDED Requirements

### Requirement: Developer validation compiles the code on the CI Python version

The full local check set SHALL include a repository-owned step that reads the Python version pinned by the CI validation workflow. When the interpreter running the local checks has a different minor version, the step SHALL compile the repository's Python sources with an interpreter of the CI version and SHALL fail when compilation fails. When the CI version cannot be read, no interpreter of that version is available, or the available interpreter reports another version, the step SHALL refuse explicitly naming both versions, without substituting a version or interpreter. The step SHALL detect only compile-time errors; runtime behaviour differences between Python versions are outside its scope and remain covered by required CI.

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
