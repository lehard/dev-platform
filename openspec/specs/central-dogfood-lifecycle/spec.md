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

### Requirement: Central reconciliation delegates to the shared lifecycle

The central source task adapter SHALL expose the supported managed-task reconciliation operation and delegate it to the shared lifecycle primitive. It SHALL not create a source-only branch, PR, publication journal, or alternative synchronization policy.

#### Scenario: Source task falls behind main

- **GIVEN** a central managed task status reports reconciliation required
- **WHEN** the operator invokes the central reconcile command
- **THEN** it delegates to the shared reconciliation lifecycle in the assigned task worktree
- **AND** subsequent validation and publication use the existing central finish path

### Requirement: Terminal dogfood success is not invalidated by self-cleanup of the caller cwd

After GitHub merge and required local reconciliation establish terminal task success, worktree cleanup SHALL NOT cause the invoking shell/runner to report the completed task as failed merely because the task worktree was its current directory. The lifecycle SHALL account for the caller context, not only the child Python process cwd.

#### Scenario: Finish is invoked from the task worktree

- **GIVEN** `dogfood_task.py finish` is launched while the caller's current directory is inside the task worktree
- **AND** the exact task PR is merged and local reconciliation succeeds
- **WHEN** post-delivery cleanup would remove that worktree
- **THEN** the lifecycle preserves a truthful terminal success result for the caller
- **AND** it does not synchronously invalidate the caller cwd in a way that produces a false `getcwd`/exit failure
- **AND** cleanup may be recorded/deferred for a later safe integration-root context if immediate removal is unsafe

#### Scenario: Deferred cleanup is retried safely

- **GIVEN** terminal delivery succeeded but worktree cleanup was deferred
- **WHEN** the supported cleanup/recovery path runs from a surviving context
- **THEN** it removes only the exact completed task worktree/branch when still safe
- **AND** repeated cleanup converges idempotently

#### Scenario: Delivery itself fails

- **WHEN** required checks, remote merge or local reconciliation has not successfully completed
- **THEN** finish remains non-zero/blocked according to the existing lifecycle
- **AND** caller-safe cleanup handling does not mask the real delivery failure

### Requirement: Dogfood source-drift diagnostics are executable through their advertised entrypoint

When central dogfood status reports source-Issue drift and recommends machine-readable JSON recovery, the emitted command SHALL be supported by the entrypoint named in the diagnostic. The machine-readable result SHALL expose bounded recorded/current revision evidence without changing the materialized OpenSpec.

#### Scenario: Status asks for JSON drift evidence

- **GIVEN** a managed task has source-Issue drift evidence
- **WHEN** `dogfood_task.py status` prints a JSON recovery instruction
- **THEN** executing that exact instruction succeeds as a read-only status operation
- **AND** it returns the bounded recorded/current revision evidence.

