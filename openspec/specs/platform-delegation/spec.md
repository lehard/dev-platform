# platform-delegation Specification

## Purpose
TBD - created by archiving change contain-delegated-write-scope. Update Purpose after archive.
## Requirements
### Requirement: Write-capable delegation carries an assigned worktree

Every write-capable subagent/subprocess delegation SHALL carry an absolute `assigned_worktree` path that is a registered git worktree of `integration/main`, distinct from the integration copy itself.

#### Scenario: Delegation without a resolvable assigned worktree
- **WHEN** `assigned_worktree` does not resolve to a registered worktree distinct from the integration copy
- **THEN** the delegation SHALL fail closed before any subagent/subprocess is launched

### Requirement: Delegated writes are contained to the assigned worktree

The platform SHALL detect whether a delegated write-capable subagent introduced changes in `integration/main` outside its `assigned_worktree`, and SHALL fail closed when it does. Where the underlying runtime exposes a real pre-write enforcement point, the platform SHALL use it instead of relying on detection alone.

#### Scenario: Delegated writer writes only inside its assigned worktree
- **GIVEN** a write-capable subagent delegated with `assigned_worktree=<worktree path>`
- **WHEN** the subagent writes only inside `assigned_worktree`
- **THEN** the delegation SHALL be reported successful
- **AND** no containment violation SHALL be recorded

#### Scenario: Delegated writer writes into integration/main
- **GIVEN** a write-capable subagent delegated with `assigned_worktree=<worktree path>`
- **WHEN** a post-delegation comparison against the pre-delegation snapshot shows a new change in `integration/main` that was not present before delegation started
- **THEN** the delegation SHALL be reported as a containment violation, not a success
- **AND** the reported message SHALL name the specific out-of-scope path(s)
- **AND** no automatic `stash`, `reset`, `clean`, or delete SHALL be applied to `integration/main`

#### Scenario: Pre-existing dirty integration/main is not touched or misreported
- **GIVEN** `integration/main` already has uncommitted changes before delegation starts
- **WHEN** the pre-delegation snapshot records those changes
- **AND** the post-delegation snapshot shows the same changes unchanged
- **THEN** those changes SHALL NOT be treated as a new containment violation
- **AND** those changes SHALL NOT be automatically stashed, reset, or deleted
- **AND** the platform SHALL be able to distinguish this pre-existing state from a newly introduced violation in its report

#### Scenario: Containment check itself fails
- **WHEN** the pre- or post-delegation snapshot step errors (for example, `git status` fails)
- **THEN** the delegation SHALL fail closed
- **AND** SHALL NOT be reported as a successful, violation-free delegation by default

### Requirement: Containment incidents are recorded locally regardless of GitHub auth

A detected containment violation SHALL be recorded as a friction event through the existing local friction mechanism, independent of GitHub authentication availability, and only after the non-mutating containment comparison has completed.

#### Scenario: GitHub authentication is unavailable
- **WHEN** a containment violation is detected
- **AND** no GitHub API credentials are available
- **THEN** the friction event SHALL still be recorded locally
- **AND** the delegation SHALL still fail closed

#### Scenario: Friction is not recorded before the safety check completes
- **WHEN** a delegation is evaluated for containment
- **THEN** no friction event SHALL be written until the pre/post snapshot comparison has produced a definitive result

