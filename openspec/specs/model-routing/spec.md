# model-routing Specification

## Purpose
TBD - created by archiving change adopt-native-model-routing. Update Purpose after archive.
## Requirements
### Requirement: Model routing occurs at execution preflight, not backlog authoring

For a managed task, the platform SHALL make the authoritative executor-routing decision after the managed OpenSpec has been materialized in the task checkout and the parent has inspected the relevant current repository context. The Development Backlog Issue and OpenSpec SHALL NOT require a concrete model ID to remain executable.

The routing preflight SHALL be bounded and SHALL consider semantic task characteristics rather than only mechanical size. Relevant characteristics include uncertainty, cross-cutting/blast-radius, failure cost, verification difficulty, contract conflicts and material unknowns discovered in current repository context.

#### Scenario: Backlog task is executed later with changed model lineup

- **GIVEN** a managed task was authored before the platform's model mapping changed
- **WHEN** the task is started and materialized later
- **THEN** routing uses the current supported platform model policy
- **AND** no edit to the backlog Issue or canonical OpenSpec is required solely to update the executor model

#### Scenario: Small diff hides high semantic risk

- **GIVEN** a task appears mechanically small but preflight discovers a public contract, lifecycle or high-cost failure boundary
- **WHEN** the parent classifies execution difficulty
- **THEN** the task is not forced into a cheap profile merely because few files or lines are expected to change

### Requirement: The platform exposes abstract execution profiles

The routing contract SHALL support at least `routine`, `standard` and `complex` execution profiles. Concrete runtime model IDs and reasoning-effort settings SHALL live in versioned platform/runtime configuration or generated agent profiles rather than durable task artifacts.

A strong parent/supervisor SHALL remain the execution entrypoint for routing-enabled work. The parent MAY retain complex/high-risk work itself and SHOULD delegate routine/standard implementation when a configured cheaper executor is available and safe.

#### Scenario: Routine task is delegated cheaply

- **GIVEN** semantic preflight classifies a task as `routine`
- **AND** a supported cheaper executor is available
- **WHEN** implementation begins
- **THEN** the parent delegates the bounded implementation to the configured routine executor
- **AND** the user is not required to choose that executor manually

#### Scenario: Complex task stays on strong profile

- **GIVEN** semantic preflight classifies the task as `complex`
- **WHEN** implementation begins
- **THEN** the platform keeps or routes the work to the configured strong profile
- **AND** it does not require an unnecessary cheap-model attempt first

### Requirement: Routing is provider-local in the first version

The platform SHALL support OpenAI-local routing when work is entered through Codex and Claude-local routing when work is entered through Claude Code. Cross-provider delegation SHALL NOT be required for the initial routing capability.

The integration SHALL use the supported project-level/native agent capabilities of the current runtime when practical and SHALL verify the actually supported runtime surface during implementation preflight rather than assuming a permanent external CLI/IDE API.

#### Scenario: Codex entrypoint selects an OpenAI executor

- **GIVEN** the user starts a managed task through a supported Codex VS Code/CLI environment
- **WHEN** routing selects a cheaper profile
- **THEN** the delegated executor uses a configured supported OpenAI model/profile
- **AND** no Claude runtime is required

#### Scenario: Claude entrypoint selects a Claude executor

- **GIVEN** the user starts a managed task through a supported Claude Code Desktop/CLI environment
- **WHEN** routing selects a cheaper profile
- **THEN** the delegated executor uses a configured supported Claude model/profile
- **AND** no OpenAI runtime is required

### Requirement: Routed writers use the platform containment invariant without unnecessary duplicate guards

A routed child that can modify repository state SHALL have a valid assigned task worktree and SHALL execute under a proven write boundary that protects integration/main and other task worktrees. The platform SHOULD prefer the current runtime's native OS-level sandbox/worktree isolation when it can prove that boundary for the actual filesystem topology.

Native containment SHALL NOT be wrapped in an additional provider-specific prevention layer merely because a legacy guard exists. A custom guarded launch or detection-only fallback SHALL be used only where native isolation is unavailable, insufficient, or not provable for the supported runtime/mode. A lightweight content-aware integration post-check SHALL remain defense in depth for routed writers.

#### Scenario: Native runtime containment is sufficient

- **GIVEN** the selected runtime exposes a proven write boundary restricted to the assigned task workspace/worktree
- **WHEN** routed implementation starts
- **THEN** the platform MAY use the native child execution path directly
- **AND** it does not require redundant provider-specific guard ceremony
- **AND** the integration post-check still runs before success is reported

#### Scenario: Native runtime containment is insufficient

- **GIVEN** a selected child can write repository state
- **BUT** the platform cannot prove an adequate native boundary for that runtime/mode
- **WHEN** routed implementation is prepared
- **THEN** the platform uses the minimal safe guarded fallback or retains implementation on the parent
- **AND** it does not claim native hard containment

### Requirement: Under-routing triggers controlled escalation

A delegated executor SHALL stop and escalate when evidence shows that the selected execution profile is insufficient. Escalation triggers SHALL include at least material OpenSpec/current-spec conflict, substantial unexpected scope growth, unexpected cross-cutting impact, materially low confidence, or repeated substantive failure to satisfy required verification after reasonable bounded attempts.

Escalation SHALL preserve useful task state: canonical OpenSpec, current assigned worktree/diff, relevant findings and verification failures, plus the reason for escalation. It SHALL NOT restart the task from scratch without a concrete need.

#### Scenario: Standard task reveals cross-cutting complexity

- **GIVEN** a task was routed to the `standard` executor
- **WHEN** implementation discovers a material cross-cutting contract or architecture problem
- **THEN** the standard executor stops broadening the solution autonomously
- **AND** the task context is handed to the configured stronger profile
- **AND** implementation resumes from the existing task state after the stronger parent reconciles the contract

#### Scenario: Failed bounded attempts cause escalation

- **GIVEN** the delegated executor has made the configured bounded substantive attempts to satisfy required checks
- **AND** the remaining failure indicates reasoning/diagnostic difficulty rather than a transient command error
- **WHEN** the attempt bound is reached
- **THEN** the work escalates instead of entering an unbounded cheap-model retry loop

### Requirement: Routing failures degrade truthfully and safely

If the preferred executor, model or subagent capability is unavailable, the workflow SHALL NOT report a delegation that did not occur. It SHALL either use an explicitly configured safe fallback/parent profile or return an actionable capability diagnostic when no safe route exists.

Model routing SHALL NOT bypass OpenSpec consistency, project checks, semantic verification, protected-main requirements or publication rules. The parent/supervisor remains responsible for assessing the delegated result before the normal completion lifecycle proceeds.

#### Scenario: Cheap executor is unavailable

- **GIVEN** routing selects a cheaper profile
- **BUT** the configured executor is unavailable in the current runtime
- **WHEN** execution continues
- **THEN** the platform uses the configured safe fallback or parent
- **AND** records/reports the actual route rather than claiming the unavailable executor was used

#### Scenario: Delegated implementation completes

- **WHEN** a routed child reports implementation complete
- **THEN** the parent evaluates the result in the task checkout
- **AND** all existing required checks and OpenSpec completion semantics still apply before publication

