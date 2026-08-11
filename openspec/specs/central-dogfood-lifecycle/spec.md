# central-dogfood-lifecycle Specification

## Purpose
TBD - created by archiving change add-central-dogfood-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Central source lifecycle configuration is explicit

The central `dev-platform` source repository SHALL commit source-owned
configuration for its integration branch, protected-main expectation, task
workspace/profile, publication mode, merge policy and lifecycle paths. Central
commands SHALL NOT derive those values from `_platform_common.py` fallback
defaults.

#### Scenario: Source configuration is present

- **WHEN** a central lifecycle command prepares or finishes a task
- **THEN** it reads the committed central source configuration
- **AND** it uses the declared multi-agent workspace path and PR publication policy

### Requirement: Managed source tasks start in an isolated workspace

The central source lifecycle SHALL provide a supported start command that
prepares an isolated feature worktree from synchronized `main`. When a managed
task package has already been materialized in the integration checkout, start
MAY transfer only that validated package into the new worktree; it SHALL fail
closed for any other integration-copy mutation and SHALL NOT stash, reset or
clean unrelated work.

#### Scenario: Clean managed intake is transferred

- **GIVEN** the only integration-copy mutation is one validated managed OpenSpec package
- **WHEN** central start is invoked with that change name
- **THEN** it runs the normal source doctor/start primitives
- **AND** transfers the package into the newly created isolated worktree
- **AND** leaves the integration copy clean on `main`

#### Scenario: Unrelated integration mutation exists

- **GIVEN** the integration copy has a change outside the named managed package
- **WHEN** central start is invoked
- **THEN** it refuses before creating or moving task state
- **AND** it does not stash, reset or delete the unrelated change

### Requirement: Central status and finish reuse publication authority

Central source status and finish commands SHALL delegate to the platform-owned
GitHub-backed publication observation and reconciliation primitives. The source
adapter SHALL not introduce a second publication journal or infer completion
from command prose.

#### Scenario: Source PR is open or green

- **WHEN** the exact task PR is pushed, draft/open, checking, auto-merge armed, or green but unmerged
- **THEN** central status reports the corresponding nonterminal authoritative state
- **AND** finish remains the resumable advance operation

#### Scenario: Source PR is merged

- **WHEN** GitHub confirms the exact task PR is `MERGED`
- **THEN** central finish performs the existing protected-main local reconciliation and task cleanup behavior
- **AND** terminal completion is reported only after that reconciliation succeeds or a cleanup result is classified as a shared-policy warning

