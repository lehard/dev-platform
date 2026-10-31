## MODIFIED Requirements

### Requirement: Write-capable delegation carries an assigned worktree

Every platform-supported write-capable subagent/subprocess delegation SHALL carry an absolute `assigned_worktree` path that resolves to a registered git worktree of the integration repository and is distinct from the integration copy itself.

#### Scenario: Delegation bypasses the supported guard

- **WHEN** a write-capable delegated runtime is invoked without either a proven native containment boundary or the supported guarded fallback
- **THEN** the platform SHALL NOT represent that invocation as platform-contained
- **AND** agent-facing guidance SHALL direct platform-managed write delegation through a supported native or fallback-contained path

#### Scenario: Delegation without a resolvable assigned worktree

- **WHEN** `assigned_worktree` does not resolve to a registered worktree distinct from the integration copy
- **THEN** the delegation SHALL fail closed before any subagent/subprocess is launched

### Requirement: Delegated writes are contained to the assigned worktree

The platform SHALL apply the strongest proven enforcement available for the selected runtime/mode and SHALL execute or bind the child to the assigned task worktree.

For supported runtimes with proven native OS-level writable-root sandboxing or native worktree isolation, that native mechanism SHOULD be the primary prevention layer. Provider-specific custom hooks/wrappers MAY remain only where they close a demonstrated gap that native containment does not cover.

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

#### Scenario: Claude structured write payload names no target

- **GIVEN** the structured-write guarded fallback is active for a Claude Code child/session
- **WHEN** a guarded tool use carries no recognized target key (`file_path`, `path` or `notebook_path`)
- **THEN** the fallback guard SHALL deny that tool use with a reason naming the missing target keys
- **AND** SHALL NOT allow an unverified write

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

### Requirement: Sandboxed Claude writers work in a disposable copy and return a patch

A platform-launched sandboxed Claude writer SHALL run in a disposable copy of the assigned task worktree containing its HEAD and current uncommitted task state, never in the task worktree or integration checkout.

#### Scenario: Sibling session advances integration main during the run
- **GIVEN** a sandboxed Claude writer is running
- **WHEN** another session fast-forwards integration `main`
- **THEN** the writer's result is still applied and no containment violation is recorded

#### Scenario: Task content changed during the run
- **WHEN** the assigned task worktree content differs from the route pre-snapshot at apply time
- **THEN** the patch is not applied, it is retained, and the dispatch fails naming the diverged paths

### Requirement: Sandboxed writer containment is proven by reproducible negative probes

The platform SHALL provide a reproducible probe command that launches a real sandboxed Claude writer against a synthetic integration repository, linked worktree and bare remote, has it attempt to write into the integration checkout, move its refs through the shared Git directory, push to the remote, call the GitHub API and read SSH, GitHub CLI and keychain credentials, and then verifies from the harness that the integration content, refs and remote are unchanged.

#### Scenario: All probes refused
- **WHEN** the probe command runs on macOS with the sandboxed writer launch
- **THEN** every probe is reported refused, the integration and remote are unchanged and the command exits zero

#### Scenario: A probe succeeds
- **WHEN** any probe action succeeds or the integration or remote changed
- **THEN** the command exits non-zero naming that probe

## ADDED Requirements

### Requirement: The assigned worktree is validated before a write-capable child launches

The platform SHALL validate the `assigned_worktree` assignment of a write-capable subagent/subprocess delegation before launching a write-capable child.

#### Scenario: Write-capable child is about to launch

- **WHEN** the platform launches a write-capable child
- **THEN** it validates the delegation's `assigned_worktree` assignment first

### Requirement: Delegation containment does not require a custom launch helper under proven native containment

The delegation containment contract SHALL NOT require one specific custom launch helper when the current runtime provides a proven native filesystem/worktree boundary that enforces the same `assigned_worktree` assignment.

#### Scenario: Runtime enforces the assignment natively

- **GIVEN** the current runtime provides a proven native filesystem/worktree boundary that enforces the `assigned_worktree` assignment
- **WHEN** a write-capable delegation launches
- **THEN** the containment contract does not require one specific custom launch helper

### Requirement: Unproven native delegation containment uses a guarded fallback or fails closed

Where native containment of a write-capable delegation cannot be proven sufficient, the platform SHALL use the minimal supported guarded fallback or fail closed/retain execution on the parent.

#### Scenario: Native containment is not proven sufficient

- **WHEN** native containment of a write-capable delegation cannot be proven sufficient
- **THEN** the platform uses the minimal supported guarded fallback or fails closed/retains execution on the parent

### Requirement: Delegated execution is reported contained only after an integration comparison

The platform SHALL perform a content-aware post-delegation integration comparison before reporting successful platform-contained execution of a delegated writer.

#### Scenario: Delegated writer finishes

- **WHEN** a delegated writer finishes
- **THEN** the platform performs a content-aware post-delegation integration comparison
- **AND** only then reports successful platform-contained execution

### Requirement: Hard delegated write containment is claimed only over resolved topology

The platform SHALL reason over resolved filesystem topology and runtime-known additional writable roots before claiming hard containment of delegated writes.

#### Scenario: Platform claims hard containment

- **WHEN** the platform claims hard containment of delegated writes
- **THEN** it has reasoned over resolved filesystem topology and runtime-known additional writable roots

### Requirement: Detection-only delegated write mode is never labeled hard prevention

For delegated writes, detection-only mode MAY remain as a bounded compatibility fallback but SHALL never be mislabeled as hard prevention.

#### Scenario: Delegated writer runs in detection-only mode

- **WHEN** a delegated writer runs in detection-only mode
- **THEN** the mode is not labeled as hard prevention

### Requirement: The sandboxed Claude writer harness builds the result in its own staging clone

The harness of a platform-launched sandboxed Claude writer SHALL build the result in its own staging clone without executing Git in the writer checkout, and SHALL apply the lifecycle write rules.

#### Scenario: Sandboxed writer run ends

- **WHEN** a platform-launched sandboxed Claude writer run ends
- **THEN** the harness builds the result in its own staging clone without executing Git in the writer checkout
- **AND** it applies the lifecycle write rules

### Requirement: The sandboxed Claude writer patch is applied only to unchanged task content

The harness of a platform-launched sandboxed Claude writer SHALL apply the resulting patch to the assigned task worktree only when task content still equals the route pre-snapshot; otherwise the harness SHALL refuse and retain the patch.

#### Scenario: Task content still equals the pre-snapshot

- **WHEN** the assigned task worktree's task content still equals the route pre-snapshot
- **THEN** the harness applies the resulting patch to the assigned task worktree

### Requirement: Integration main moving is not a sandboxed Claude writer containment violation

Integration `main` moving during the run of a platform-launched sandboxed Claude writer SHALL NOT be classified as a containment violation of that writer.

#### Scenario: Integration main moves during the writer run

- **WHEN** integration `main` moves during the run of a platform-launched sandboxed Claude writer
- **THEN** it is not classified as a containment violation of that writer

### Requirement: The sandboxed writer probe command never prints the writer credential

The sandboxed writer containment probe command SHALL never print the writer credential.

#### Scenario: Probe command runs

- **WHEN** the sandboxed writer containment probe command runs
- **THEN** its output never contains the writer credential

### Requirement: The sandboxed writer probe command fails when a probe succeeds

The sandboxed writer containment probe command SHALL exit non-zero when any probe succeeded or any harness-side check changed.

#### Scenario: A probe succeeds or a harness-side check changed

- **WHEN** any probe succeeded or any harness-side check changed
- **THEN** the sandboxed writer containment probe command exits non-zero
