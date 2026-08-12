# platform-delegation Specification

## Purpose
TBD - created by archiving change contain-delegated-write-scope. Update Purpose after archive.
## Requirements
### Requirement: Write-capable delegation carries an assigned worktree

Every platform-supported write-capable subagent/subprocess delegation SHALL carry an absolute `assigned_worktree` path that resolves to a registered git worktree of the integration repository and is distinct from the integration copy itself. The platform SHALL validate that assignment before launching a write-capable child.

The containment contract SHALL NOT require one specific custom launch helper when the current runtime provides a proven native filesystem/worktree boundary that enforces the same assignment. Where native containment cannot be proven sufficient, the platform SHALL use the minimal supported guarded fallback or fail closed/retain execution on the parent.

#### Scenario: Delegation bypasses the supported guard

- **WHEN** a write-capable delegated runtime is invoked without either a proven native containment boundary or the supported guarded fallback
- **THEN** the platform SHALL NOT represent that invocation as platform-contained
- **AND** agent-facing guidance SHALL direct platform-managed write delegation through a supported native or fallback-contained path

#### Scenario: Delegation without a resolvable assigned worktree

- **WHEN** `assigned_worktree` does not resolve to a registered worktree distinct from the integration copy
- **THEN** the delegation SHALL fail closed before any subagent/subprocess is launched

### Requirement: Delegated writes are contained to the assigned worktree

The platform SHALL apply the strongest proven enforcement available for the selected runtime/mode, SHALL execute or bind the child to the assigned task worktree, and SHALL perform a content-aware post-delegation integration comparison before reporting successful platform-contained execution.

For supported runtimes with proven native OS-level writable-root sandboxing or native worktree isolation, that native mechanism SHOULD be the primary prevention layer. The platform SHALL reason over resolved filesystem topology and runtime-known additional writable roots before claiming hard containment. Provider-specific custom hooks/wrappers MAY remain only where they close a demonstrated gap that native containment does not cover. Detection-only mode MAY remain as a bounded compatibility fallback but SHALL never be mislabeled as hard prevention.

#### Scenario: Platform-controlled Codex supports hard writable-root sandboxing

- **GIVEN** the platform selects a supported Codex delegated child launch
- **AND** the supported runtime exposes a writable-root OS sandbox
- **AND** protected repository paths resolve outside all runtime-known additional writable roots
- **WHEN** the child is launched as hard-contained
- **THEN** the writable boundary SHALL prevent mutation of protected repository paths outside `assigned_worktree`
- **AND** inability to establish that policy SHALL fail closed or be explicitly downgraded before launch
- **AND** a downgraded run SHALL NOT retain a hard-containment label

#### Scenario: Claude native sandbox/worktree isolation protects the assigned task

- **GIVEN** the supported Claude Code runtime exposes a proven native filesystem sandbox or worktree-isolated child mode
- **AND** the actual child permissions keep protected repository paths outside its write boundary
- **WHEN** the child runs
- **THEN** the platform MAY rely on that native boundary as the primary prevention layer
- **AND** SHALL NOT require legacy structured-write hooks merely to duplicate the same boundary
- **AND** SHALL still run the content-aware integration post-check

#### Scenario: Codex sandbox exposes additional writable temporary roots

- **GIVEN** the platform controls a Codex delegated child launch
- **AND** the runtime's workspace-write sandbox is known to allow one or more system temporary roots in addition to the assigned worktree
- **WHEN** the platform evaluates the enforcement tier
- **THEN** it SHALL normalize the protected repository paths and known additional writable roots before claiming `HARD`
- **AND** SHALL NOT describe the sandbox as “writable only inside assigned_worktree” unless that is actually proven

#### Scenario: Protected integration repository overlaps a runtime-writable temp root

- **GIVEN** `integration_root` resolves inside `/tmp`, `$TMPDIR`, or another proven runtime-writable temporary root
- **WHEN** Codex containment is evaluated
- **THEN** the run SHALL NOT be classified `HARD`
- **AND** `require_hard=True` SHALL fail closed before child launch
- **AND** an allowed fallback SHALL be explicitly classified `DETECTION_ONLY`

#### Scenario: Normal repository topology is outside runtime-writable temp roots

- **GIVEN** the supported Codex runtime exposes a proven OS writable-root sandbox
- **AND** protected repository paths resolve outside all known runtime-added writable roots
- **WHEN** hard containment is established
- **THEN** the platform MAY classify the run `HARD`
- **AND** SHALL still perform the post-delegation content-aware integration check as defense in depth

#### Scenario: Temporary-root path is reached through a symlink

- **GIVEN** a configured integration/worktree path resolves through symlinks into a runtime-writable temporary root
- **WHEN** containment capability is evaluated
- **THEN** the resolved filesystem topology SHALL be used
- **AND** textual path differences SHALL NOT permit an unsafe `HARD` classification

#### Scenario: Claude structured write targets outside the assignment

- **GIVEN** native containment is insufficient and the platform selects the structured-write guarded fallback for a Claude Code child/session
- **WHEN** a structured filesystem write tool resolves a target outside `assigned_worktree`
- **THEN** the fallback guard SHALL deny that tool use before the write occurs

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

