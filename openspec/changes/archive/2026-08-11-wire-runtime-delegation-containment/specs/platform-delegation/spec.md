## MODIFIED Requirements

### Requirement: Write-capable delegation carries an assigned worktree

Every platform-supported write-capable subagent/subprocess delegation SHALL carry an absolute `assigned_worktree` path that is a registered git worktree of the integration repository, distinct from the integration copy itself. A platform-supported write delegation SHALL enter through the guarded delegation path that validates this assignment before child execution.

#### Scenario: Delegation bypasses the supported guard

- **WHEN** a write-capable delegated runtime is invoked without the platform guarded delegation path
- **THEN** the platform SHALL NOT represent that invocation as platform-contained
- **AND** agent-facing guidance SHALL direct platform-managed write delegation through the guarded path

#### Scenario: Delegation without a resolvable assigned worktree

- **WHEN** `assigned_worktree` does not resolve to a registered worktree distinct from the integration copy
- **THEN** the delegation SHALL fail closed before any subagent/subprocess is launched

### Requirement: Delegated writes are contained to the assigned worktree

The platform SHALL apply the strongest proven enforcement tier available for a supported write-capable delegated runtime, SHALL execute the child with `cwd=assigned_worktree`, and SHALL perform a content-aware post-delegation integration comparison before reporting success. Where hard prevention cannot be proven, the platform SHALL label the run detection-only and apply the stricter dirty-integration precondition.

#### Scenario: Platform-controlled Codex supports hard writable-root sandboxing

- **GIVEN** the platform controls a Codex delegated child launch
- **AND** the supported runtime exposes a writable-root OS sandbox
- **WHEN** the child is launched as hard-contained
- **THEN** the writable repository root SHALL be restricted to `assigned_worktree`
- **AND** inability to establish that policy SHALL fail closed or be explicitly downgraded before launch
- **AND** a downgraded run SHALL NOT retain a hard-containment label

#### Scenario: Claude structured write targets outside the assignment

- **GIVEN** the platform controls a Claude Code child/session with supported pre-write hooks
- **WHEN** a structured filesystem write tool resolves a target outside `assigned_worktree`
- **THEN** the guard SHALL deny that tool use before the write occurs

#### Scenario: Claude shell-capable delegation has no real OS filesystem sandbox

- **WHEN** arbitrary shell execution is available and no real OS writable-root boundary is proven
- **THEN** the platform SHALL treat that delegation as detection-only
- **AND** SHALL NOT claim command-text inspection alone as hard filesystem containment

#### Scenario: Detection-only writer starts while integration is dirty

- **GIVEN** the selected runtime/enforcement tier is detection-only
- **AND** the integration checkout has uncommitted state before delegation
- **WHEN** the platform prepares to launch the writer
- **THEN** it SHALL fail closed before child execution
- **AND** SHALL leave the pre-existing integration state untouched

#### Scenario: Delegated writer writes only inside its assigned worktree

- **GIVEN** a supported write-capable delegation with a valid `assigned_worktree`
- **WHEN** runtime enforcement is configured according to its tier
- **AND** the content-aware post-check finds no integration mutation
- **THEN** the delegation MAY be reported successful
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

#### Scenario: Child process fails

- **WHEN** the delegated child exits non-zero, is cancelled, or otherwise fails
- **THEN** the platform SHALL still execute the post-delegation containment comparison
- **AND** a detected integration mutation SHALL be reported as a containment violation in addition to the child failure

### Requirement: Containment incidents are recorded locally regardless of GitHub auth

A detected containment violation SHALL be recorded as a friction event through the existing local friction mechanism, independent of GitHub authentication availability, and only after the non-mutating containment comparison has completed. Hard-prevention refusal and detection-only dirty-integration refusal MAY also be recorded as structured safety friction when useful, but SHALL NOT require GitHub access.

#### Scenario: Runtime prevention is bypassed or misconfigured but post-check catches mutation

- **WHEN** the content-aware post-check detects integration mutation after a supposedly contained child
- **THEN** the delegation SHALL fail closed
- **AND** the local friction record SHALL identify the affected path(s) and claimed enforcement tier
- **AND** the platform SHALL NOT automatically stash, reset, clean, or delete the integration changes

#### Scenario: GitHub authentication is unavailable

- **WHEN** a containment violation is detected
- **AND** no GitHub API credentials are available
- **THEN** the friction event SHALL still be recorded locally
- **AND** the delegation SHALL still fail closed

#### Scenario: Friction is not recorded before the safety check completes

- **WHEN** a delegation is evaluated for containment
- **THEN** no friction event SHALL be written until the pre/post snapshot comparison has produced a definitive result

## ADDED Requirements

### Requirement: Integration snapshots detect content changes, not only Git status labels

The containment snapshot SHALL be sufficient to detect relevant integration working-tree/index/untracked content changes even when the same path remains in the same porcelain status category before and after delegation.

#### Scenario: Pre-existing modified tracked file is changed again

- **GIVEN** `integration/main` contains a tracked path already reported modified before delegation
- **WHEN** the delegated writer changes that path's contents while its porcelain status code remains the same
- **THEN** the post-check SHALL classify the path as newly changed during the delegation window
- **AND** SHALL report a containment violation

#### Scenario: Pre-existing dirty path is actually unchanged

- **GIVEN** a hard-contained delegated run is allowed to start while integration already contains dirty state
- **WHEN** the relevant path/index/untracked fingerprints are identical before and after delegation
- **THEN** that state SHALL remain classified as pre-existing unchanged state
- **AND** SHALL NOT be reported as a new containment violation

#### Scenario: Untracked content changes without path disappearance

- **GIVEN** an untracked path exists before delegation
- **WHEN** its contents change during delegation but the path remains untracked
- **THEN** the content-aware snapshot SHALL detect the change
- **AND** SHALL report the affected path

#### Scenario: Snapshot cannot inspect required state

- **WHEN** a required pre- or post-snapshot fingerprint cannot be captured consistently
- **THEN** containment evaluation SHALL fail closed
- **AND** SHALL NOT report the delegation as violation-free by default
