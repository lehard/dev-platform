# model-routing Specification

## Purpose
TBD - created by archiving change adopt-native-model-routing. Update Purpose after archive.
## Requirements
### Requirement: The platform exposes abstract execution profiles

The routing contract SHALL support at least `routine`, `standard` and `complex` execution profiles, reachable either from an authored abstract start tier (`R1` -> `routine`, `R2` -> `standard`, `R3` -> `complex`) or from an explicit override. Concrete runtime model IDs and reasoning-effort settings SHALL live in versioned platform/runtime configuration or generated agent profiles rather than durable task artifacts.

Provider-local delegation, including a strong parent/supervisor, remains a supported execution capability, but a strong parent SHALL NOT be a mandatory entrypoint for every routing-enabled managed task: execution MAY begin directly on the tier-recommended executor. The parent MAY retain complex/high-risk work itself and SHOULD delegate routine/standard implementation when a configured cheaper executor is available and safe. If work starts on a stronger-than-recommended session, the platform MAY down-route through the existing supported provider-local child path instead of requiring ceremonial re-delegation.

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

#### Scenario: R2 starts directly on the recommended executor

- **GIVEN** a managed task recommends `R2`
- **AND** the configured balanced provider-local executor is available
- **WHEN** execution starts directly on that executor
- **THEN** the task begins without first running Sol/Opus as a routing supervisor and without ceremonial strong-parent delegation
- **AND** normal containment, verification and publication invariants remain authoritative
- **AND** provider-local delegation remains available as a secondary capability if needed later

#### Scenario: Task opened on a stronger-than-recommended session

- **GIVEN** a managed task recommends `R2`
- **AND** execution is opened on a stronger-than-recommended provider-local session
- **WHEN** the platform evaluates the entrypoint
- **THEN** it MAY down-route through the existing supported provider-local delegation/fallback path
- **AND** normal containment and verification invariants remain authoritative

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

After the managed package is materialized, the executor SHALL perform a bounded freshness check against the current repository/spec state before implementation, confirming the authored start tier or escalating when newly discovered evidence satisfies a frontier trigger. It SHALL NOT require a strong parent to repeat the full routing assessment before implementation solely because execution has begun.

More broadly, a delegated executor SHALL stop and escalate whenever evidence shows that the selected execution profile is insufficient. Escalation triggers SHALL include at least a newly discovered frontier hard trigger, material OpenSpec/current-spec conflict, substantial unexpected scope growth, unexpected cross-cutting impact, materially low confidence, or repeated substantive failure to satisfy required verification after reasonable bounded attempts.

Escalation SHALL preserve useful task state: canonical OpenSpec, current assigned worktree/diff, relevant findings and verification failures, plus the reason for escalation. It SHALL NOT restart the task from scratch without a concrete need. Downgrade below the authored tier is not required by this version.

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

#### Scenario: Current repo reveals hidden frontier complexity

- **GIVEN** an authored `R2` task has been materialized
- **WHEN** freshness inspection discovers a supported frontier trigger absent from authoring context
- **THEN** the executor records the new evidence and escalates to the configured `R3` path
- **AND** useful task state is preserved

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

### Requirement: Managed routing recommends an abstract start tier during authoring

For a managed task, the platform SHALL record a provider-neutral recommended start tier during managed-task authoring after the accepted intent has been reconciled with a bounded targeted inspection of relevant current repository context. The recommendation SHALL be part of task execution metadata, not a concrete runtime model requirement.

The human-facing Development Backlog Issue title SHALL expose the recommendation as a compact abstract prefix so the user can select the intended starting capability without opening the Issue. Concrete model IDs SHALL NOT be embedded in the durable Issue/OpenSpec solely for routing and SHALL remain governed by current versioned runtime/platform mapping.

The first production policy SHALL support `R2` balanced and `R3` frontier recommendations. `R1` economy MAY be represented as a reserved tier but SHALL NOT be recommended for production work until a later accepted evidence-gated change enables it.

#### Scenario: Ordinary well-specified managed task

- **GIVEN** the accepted task is well specified after bounded repository inspection
- **AND** no frontier hard trigger is present
- **WHEN** the managed package is authored
- **THEN** the recommended start tier is `R2`
- **AND** the Issue title exposes `[R2]`
- **AND** no concrete Claude/OpenAI model ID is required in the managed contract

#### Scenario: Frontier work has explicit reasoning evidence

- **GIVEN** authoring identifies a supported frontier hard trigger
- **WHEN** the managed package is authored
- **THEN** the recommendation MAY be `R3`
- **AND** the routing evidence records the concrete trigger/rationale
- **AND** the Issue title exposes `[R3]`

### Requirement: Frontier routing is trigger-based rather than risk-size based

`R2` SHALL be the default production execution tier. Selecting `R3` SHALL require evidence that additional reasoning capability is plausibly outcome-changing, such as unresolved architecture, materially unknown diagnosis, weak verification combined with high consequence, novel cross-system interaction without an established pattern, trustworthy history of comparable R2 escalation, or a prior substantive balanced failure for reasoning/diagnostic causes.

Expected diff size, number of files, public visibility, blast radius or failure cost SHALL NOT by themselves require `R3`. The platform MAY increase reasoning effort or assurance while retaining `R2`.

#### Scenario: High-blast-radius but mechanically clear change

- **GIVEN** a change affects an important shared contract
- **BUT** the intended behavior is clear and objectively verifiable
- **AND** no frontier hard trigger exists
- **WHEN** routing is authored
- **THEN** the task remains eligible for `R2`
- **AND** assurance MAY be high independently

### Requirement: Execution tier, reasoning effort and assurance are independent routing dimensions

The platform SHALL represent the recommended execution tier separately from reasoning-effort guidance and assurance/verification depth. A high assurance requirement SHALL NOT automatically select a frontier executor. Runtime-specific model and effort values remain replaceable configuration/provenance rather than durable product requirements.

#### Scenario: Balanced executor with elevated safeguards

- **GIVEN** a task is semantically suitable for balanced execution
- **AND** its failure consequence requires stronger verification
- **WHEN** the task is authored/executed
- **THEN** it MAY use `R2` with elevated effort and/or high assurance
- **AND** the high assurance does not itself force `R3`

### Requirement: Routing v2 reuses truthful execution provenance

Routing v2 SHALL reuse the bounded routing/execution provenance delivered by `adopt-gh-aw-process-automation` and SHALL NOT create a parallel run/tracing state machine. Planned tier, actual execution participants/models/effort where provable, verification outcome, fallback and escalation SHALL remain distinguishable so later calibration can evaluate routing without fabricating counterfactual success.

#### Scenario: Planned and actual routes differ

- **GIVEN** a task was authored as `R2`
- **AND** actual execution later escalates or falls back
- **WHEN** provenance is recorded
- **THEN** the planned recommendation and actual execution path remain distinguishable
- **AND** later analysis can attribute the escalation without rewriting the managed task contract

