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

### Requirement: Model routing preserves truthful bounded execution provenance

For each routed non-trivial managed task, the platform SHALL preserve bounded execution provenance sufficient to distinguish the supervisor from any delegated executor that actually ran. The provenance SHALL reuse the existing routing/execution record rather than create a parallel tracing state machine.

For each participant where the information is applicable and available, provenance SHOULD represent the runtime/provider, participant role, execution profile, model identity, reasoning effort, bounded execution identifier and parent/child relationship. Model and reasoning-effort fields SHALL carry enough source/status information to distinguish platform-selected/configured values from runtime-confirmed values and unknown values.

Free-form model self-identification SHALL NOT be the authoritative source for model or effort provenance. A route that was merely prepared SHALL NOT be represented as an executed child. Fallback and escalation SHALL preserve the actual execution path rather than the preferred path that failed to run.

The concrete runtime adapters SHALL be verified against the supported Codex and Claude Code surfaces at implementation preflight. If a runtime does not reliably expose a desired field, the platform SHALL degrade truthfully by recording that field as unknown or only as selected/configured; it SHALL NOT scrape unstable UI text or infer effective execution state from an unsupported assumption solely to make the record complete.

#### Scenario: Routed Codex executor actually runs

- **GIVEN** Codex routing selects a routine or standard executor
- **WHEN** the platform-owned Codex launch actually runs the selected executor
- **THEN** the routing record preserves the actual executed child participant and the platform-selected model/profile
- **AND** reasoning effort is marked selected/configured or runtime-confirmed only according to evidence available from the supported current Codex runtime
- **AND** any unavailable effective effort remains unknown rather than inferred

#### Scenario: Native Claude subagent actually runs

- **GIVEN** Claude routing selects a routine or standard child and emits a native Agent hand-off
- **WHEN** the supervisor actually invokes that Agent and records the returned execution identifier
- **THEN** the routing record preserves the executed Claude child participant, its selected model/profile/effort and returned bounded agent identifier
- **AND** selected values are not mislabeled as runtime-confirmed unless the supported runtime also confirms them

#### Scenario: Preferred delegated executor is unavailable

- **GIVEN** routing selected a lower-cost executor
- **BUT** the current runtime cannot safely launch or confirm that child
- **WHEN** work is retained by or falls back to the parent
- **THEN** provenance reports the actual parent/fallback execution
- **AND** does not create an executed child participant for the unavailable route

#### Scenario: Routed work escalates

- **GIVEN** a delegated executor actually performed bounded work and then triggered escalation
- **WHEN** the stronger parent resumes the task
- **THEN** provenance may contain both real participants and the escalation relationship
- **AND** later friction can be attributed to the appropriate participant or to the overall run when the locus is ambiguous

### Requirement: Execution provenance remains replaceable across runtime/model changes

Execution provenance SHALL describe a specific task execution rather than become a durable model requirement of the backlog Issue or canonical product specification. Concrete model IDs, reasoning-effort vocabulary and runtime-specific identifiers remain replaceable execution metadata governed by the current supported platform/runtime policy.

Historical provenance MAY preserve the model/runtime values that actually or reportedly applied to that execution, but a later change to the supported model lineup SHALL NOT require editing old Development Backlog Issues or accepted OpenSpec requirements solely to rename current executor models.

#### Scenario: Model policy changes after an execution

- **GIVEN** a completed or recorded task execution used an older supported model mapping
- **WHEN** the platform later changes its current model-routing policy
- **THEN** historical execution provenance retains the truthful historical values/source status
- **AND** future executions use the new current policy without rewriting the managed task contract

### Requirement: Codex execution provenance is verified against a real live run

The "Routed Codex executor actually runs" scenario for truthful bounded execution provenance SHALL be verified at least once against a real, live `codex` CLI invocation through the platform-owned `dispatch_codex()`/`run_codex()` path, not solely through simulated stdout event lines in unit tests.

#### Scenario: Live Codex delegation confirms real provenance capture

- **GIVEN** a real authenticated `codex` CLI is available and a routine/standard Codex route is prepared for a real managed task
- **WHEN** `run_codex()` launches that route through the real CLI
- **THEN** the resulting `execution.participant` carries a real bounded execution identifier captured from the live `--json` event stream
- **AND** model/reasoning-effort source/status reflect only what the live run actually confirmed, with no field upgraded to `runtime-confirmed` without live evidence

### Requirement: Routed Codex execution has single-writer ownership per assigned worktree

The model-routing lifecycle SHALL prevent more than one active write-capable Codex executor from owning the same assigned worktree at the same time. Launch ownership SHALL remain held until the prior writer is known to have exited or has been terminated and reaped.

#### Scenario: Second writer is requested while the first is active

- **GIVEN** a write-capable Codex executor currently owns an assigned worktree
- **WHEN** another routed Codex launch targets the same worktree
- **THEN** the second launch is refused before it can write
- **AND** the existing writer remains the only active writer for that worktree

#### Scenario: Prior launch state is ambiguous

- **WHEN** the platform cannot safely prove that the previous writer has exited
- **THEN** it does not release single-writer ownership
- **AND** a new write-capable launch fails closed with an actionable diagnostic

### Requirement: Abnormal delegated return leaves truthful execution state

If a routed Codex launch returns abnormally after starting a writer, routing provenance SHALL NOT represent the handoff as cleanly complete until the writer lifecycle is resolved.

#### Scenario: Parent path fails after child launch

- **WHEN** a routed launch encounters timeout, cancellation, stream failure or another abnormal return after the child started
- **THEN** execution provenance records the real failed/abnormal outcome
- **AND** the worktree is not made eligible for a new writer while the previous writer remains live or ambiguous

### Requirement: Managed execution provenance captures comparable efficiency evidence

For non-trivial managed execution, the platform SHALL preserve bounded runtime-efficiency evidence in the existing routing/execution provenance path rather than creating a parallel observability state machine.

The platform SHALL record execution timing from its own execution boundary. Runtime/provider-supplied usage fields such as input/prompt tokens, cache-read tokens, fresh/computed input tokens, output tokens, total tokens, and model-request/turn counts MAY be recorded when the supported runtime exposes authoritative values. Optional measurements SHALL preserve enough source/status information to distinguish measured/confirmed values from unavailable or unknown values.

Missing efficiency evidence SHALL NOT be represented as zero and SHALL NOT make an otherwise valid task execution fail solely because a provider does not expose a usage metric.

#### Scenario: Runtime exposes authoritative usage

- **GIVEN** a managed executor returns supported structured usage evidence
- **WHEN** the platform records the execution outcome
- **THEN** the compatible normalized efficiency fields are preserved with truthful source/status
- **AND** platform-measured elapsed time is preserved alongside them
- **AND** no prompt, chain-of-thought or full transcript is required

#### Scenario: Runtime does not expose token usage

- **GIVEN** a managed executor completes but the supported runtime exposes no reliable token breakdown
- **WHEN** execution provenance is finalized
- **THEN** elapsed time and the available lifecycle outcome are still recorded
- **AND** unsupported usage fields remain unknown/absent rather than guessed or set to zero
- **AND** completion is not rejected solely because usage metadata is unavailable

### Requirement: Efficiency evidence reuses existing execution outcomes

Efficiency measurement SHALL reuse the existing provider/model/profile provenance and the existing verification, retry/escalation/fallback, human-intervention, containment, abnormal-termination and recovery evidence where those facts already exist. It SHALL NOT introduce a competing task/execution status machine.

#### Scenario: Execution escalates

- **GIVEN** an R2 execution performs bounded work and then escalates
- **WHEN** efficiency evidence is aggregated
- **THEN** the actual elapsed/usage evidence for the performed path remains attributable to the real execution
- **AND** the existing escalation/final-outcome provenance remains authoritative

### Requirement: Efficiency evidence remains runtime-neutral and historically compatible

The canonical efficiency schema SHALL NOT depend on DeepSeek Harness, Cordis, or another optional runtime implementation. Historical execution records that predate efficiency fields SHALL remain readable and SHALL be treated as missing evidence rather than invalid or zero-valued observations. The schema SHALL compare a model-request count across runtimes only when each contributing adapter has authoritative evidence that its counted event has that same semantic identity. Runtime-local turn, assistant-message or step counters MAY be retained as bounded evidence but SHALL NOT be silently normalized into a cross-runtime model-request metric. Historical ambiguous counters SHALL remain readable without being upgraded to stronger semantics.

#### Scenario: Historical record is analyzed

- **GIVEN** a prior execution record has no efficiency fields
- **WHEN** a baseline report reads it
- **THEN** the record may still contribute compatible outcome facts
- **AND** unavailable efficiency measurements are classified as missing
- **AND** no fabricated values are introduced

#### Scenario: Runtime event meanings differ

- **GIVEN** two runtimes expose different event types whose one-to-one relationship to model requests is not proven
- **WHEN** efficiency evidence is normalized
- **THEN** the platform does not aggregate those counters as one comparable metric
- **AND** unavailable canonical request counts remain unknown rather than fabricated.

### Requirement: Baseline reporting exposes sample adequacy

The execution-efficiency baseline SHALL distinguish launched executions from verified managed executions. A decision-quality `sufficient` status SHALL NOT be produced solely because the launched-execution count reaches the sample guideline. The first decision-quality gate SHALL require at least 15 verified managed executions and SHALL expose verification/metric coverage so sparse or incompatible evidence remains visible.

#### Scenario: Launch count is high but verification coverage is low

- **GIVEN** at least 15 managed executions were launched
- **AND** fewer than 15 have verified completion evidence
- **WHEN** the baseline report is generated
- **THEN** it remains `insufficient`
- **AND** it reports launched and verified/eligible counts separately.

#### Scenario: Baseline sample is too small

- **GIVEN** only a small or sparsely populated execution sample exists
- **WHEN** the baseline report is generated
- **THEN** it reports the available observations and missing-field coverage
- **AND** it labels the evidence insufficient rather than claiming a reliable improvement or regression

### Requirement: Baseline collection does not self-optimize execution

This change SHALL collect and report evidence only. It SHALL NOT automatically switch runtimes, change routing tiers, enable R1, enforce token/time kill budgets, or self-modify routing policy based on the collected sample.

#### Scenario: High-cost execution is observed

- **WHEN** the report observes an unusually expensive or long execution
- **THEN** the observation is retained for analysis
- **AND** no new automatic routing or cancellation policy is inferred by this change alone

