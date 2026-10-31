# model-routing Specification

## Purpose
Define provider-neutral model routing, escalation, and evidence requirements for managed task execution.

## Requirements

### Requirement: The platform exposes abstract execution profiles

The routing contract SHALL support at least `routine`, `standard` and `complex` execution profiles, reachable either from an authored abstract start tier (`R1` -> `routine`, `R2` -> `standard`, `R3` -> `complex`) or from an explicit override.

#### Scenario: Routine task stays on the supervisor by default

- **GIVEN** semantic preflight classifies a task as `routine` or `standard`
- **AND** no delegation is explicitly requested
- **WHEN** implementation begins
- **THEN** the supervisor implements the task itself under a supervisor-retained plan
- **AND** the user is not required to choose an executor manually

#### Scenario: Routine task is delegated cheaply

- **GIVEN** semantic preflight classifies a task as `routine` or `standard`
- **AND** delegation is explicitly requested and a supported cheaper executor is available
- **WHEN** implementation begins
- **THEN** the bounded implementation is delegated to the configured routine/standard executor

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

`R2` SHALL be the default production execution tier.

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

#### Scenario: Routed Codex executor actually runs

- **GIVEN** Codex routing selects a routine or standard executor
- **WHEN** the platform-owned Codex launch actually runs the selected executor
- **THEN** the routing record preserves the actual executed child participant and the platform-selected model/profile
- **AND** reasoning effort is marked selected/configured or runtime-confirmed only according to evidence available from the supported current Codex runtime
- **AND** any unavailable effective effort remains unknown rather than inferred

#### Scenario: Native Claude subagent actually runs

- **GIVEN** Claude routing selects a routine or standard child and emits a native Agent hand-off
- **AND** the supported Claude runtime exposes no platform-verifiable launch receipt
- **WHEN** the supervisor records the returned agent identifier
- **THEN** the routing record preserves it only as a self-reported claim with its selected model/profile and unknown effort
- **AND** the record does not mark the child as launched or as an executed participant

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

The canonical efficiency schema SHALL NOT depend on any optional runtime implementation.

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

### Requirement: Routing calibration reuses the existing execution baseline evidence path

The platform SHALL support bounded read-only calibration of the current R2/R3 routing rubric from existing managed-task routing/execution records and verification evidence. Calibration SHALL reuse the current routing-record/baseline scanning path and SHALL NOT introduce a parallel execution database, tracing backend, transcript store or calibration state machine.

#### Scenario: Verified execution lacks comparable efficiency usage

- **GIVEN** a managed execution has truthful authored routing data, actual route/outcome and verification evidence
- **AND** token/request usage is unavailable or not cross-runtime comparable
- **WHEN** routing calibration evaluates the execution
- **THEN** the execution may still contribute routing-outcome evidence
- **AND** unavailable efficiency metadata remains unknown rather than excluding an otherwise usable routing outcome

### Requirement: Calibration distinguishes authored route from actual execution outcome

For each usable execution, calibration SHALL preserve authored start tier and rubric/task-family context where present, actual execution/fallback/escalation path, verification outcome, and provider/model source status where provable. Missing fields SHALL remain missing or unknown.

#### Scenario: Authored R2 completes without frontier escalation

- **GIVEN** an authored `R2` execution completes required verification without `R3` escalation
- **WHEN** calibration aggregates outcomes
- **THEN** it contributes positive evidence for the current R2 path in its recorded context
- **AND** it is counted separately from direct R3 executions and escalated executions

#### Scenario: R2 escalates and then succeeds

- **GIVEN** an authored `R2` execution has a real R2 attempt
- **AND** the path later escalates to `R3` and completes successfully
- **WHEN** calibration aggregates outcomes
- **THEN** the initial R2 path and final success remain distinguishable
- **AND** an escalation reason is reported only when the existing provenance proves it

#### Scenario: Legacy or partial record

- **GIVEN** a historical routing record lacks an authored tier, model confirmation, escalation reason or another optional field
- **WHEN** calibration reads it
- **THEN** supported facts may still contribute to compatible counts
- **AND** missing values are not converted to defaults or guesses

### Requirement: Calibration avoids unsupported counterfactual claims

Calibration SHALL NOT infer that `R3` was necessary merely because a direct R3 execution succeeded. It SHALL NOT label a direct R3 execution as over-routing without additional counterfactual evidence. Counterfactual replay is not required for the first calibration version.

#### Scenario: Direct frontier execution succeeds

- **GIVEN** a task was authored and executed directly as `R3`
- **WHEN** calibration analyzes the result
- **THEN** it is recorded as successful direct R3 execution
- **AND** the report does not claim that R2 would have failed or succeeded

### Requirement: Calibration exposes routing-specific sample adequacy and tradeoffs

The calibration report SHALL always expose observation counts and coverage and SHALL include at least:

- authored tier distribution and frontier exposure;
- verified R2 success without R3 escalation;
- R2-to-R3 escalation rate/path and known reason distribution;
- success after escalation;
- fallback/abnormal/unknown outcome counts;
- verification, first-pass and human-intervention signals only where current evidence supports them truthfully.

#### Scenario: Global sample is usable but one family is small

- **GIVEN** the overall routing sample is adequate for a bounded global review
- **AND** one task family has too few usable executions
- **WHEN** the report renders breakdowns
- **THEN** the global report may be usable
- **AND** the small family is explicitly marked insufficient for family-specific policy advice

#### Scenario: Current real sample is insufficient

- **GIVEN** the current verified routing sample lacks adequate coverage
- **WHEN** the first calibration report is produced
- **THEN** the report returns `insufficient evidence / no policy change`
- **AND** implementation of the reporting capability is not considered blocked merely because more executions must accumulate

### Requirement: Calibration remains advisory

Calibration MAY produce a human-readable candidate decision to keep or change rubric rules, hard triggers, effort/assurance defaults or model mapping. Any actual policy change SHALL require a separate explicit reviewed managed change.

Calibration SHALL NOT automatically modify routing policy, enable R1, create Development Backlog tasks, dispatch remediation, or introduce a learned router.

#### Scenario: Report recommends a rubric change

- **GIVEN** the calibration report has adequate evidence to suggest a concrete rubric or hard-trigger adjustment
- **WHEN** the report is produced
- **THEN** it states the candidate change as human-readable advice only
- **AND** it does not edit routing policy files, `.dev-platform.toml`, the rubric or model mapping
- **AND** it does not create a Development Backlog task, dispatch remediation or enable a learned router

#### Scenario: Evidence supports keeping the current policy

- **GIVEN** the calibration report finds no change is warranted or the sample is insufficient
- **WHEN** the report is produced
- **THEN** it records `no change` or `insufficient evidence / no policy change` as advisory output
- **AND** any later policy change still requires a separate explicit reviewed managed change

### Requirement: Bulk repository context may be delegated to a cheaper read-only worker

The platform MAY delegate question-directed bulk repository reads from an already selected managed-task executor to a provider-local read-only context worker. This auxiliary operation SHALL remain distinct from the managed task start tier: using a routine-profile context worker SHALL NOT by itself classify or rewrite the managed task as R1.

#### Scenario: Strong session needs a narrow answer from broad source context

- **GIVEN** an R2 or R3 execution needs to inspect a bounded set of large repository files for a specific question
- **AND** a supported cheaper provider-local read-only worker is available
- **WHEN** context delegation is selected
- **THEN** the worker receives the question and bounded repository scope
- **AND** returns compact structured evidence to the parent
- **AND** the managed task keeps its existing R2/R3 execution identity

#### Scenario: Exact source detail is needed

- **GIVEN** editing, debugging, architecture reasoning or exact verification requires source detail
- **WHEN** the parent needs a targeted file/range
- **THEN** a direct targeted read remains available
- **AND** context delegation does not force an unnecessary summarization hop

### Requirement: Context delegation is read-only and fails open truthfully

A supported context worker path SHALL NOT grant repository write capability. If the runtime cannot provide the supported read-only delegation, the worker fails, or its result is materially low confidence, the platform SHALL expose a bounded direct-read fallback and SHALL NOT claim successful delegation.

Read-only context delegation SHALL NOT require write-containment ceremony solely for consistency with write-capable executors.

#### Scenario: Context worker cannot run

- **GIVEN** the selected runtime lacks the required read-only worker surface or the delegated operation fails
- **WHEN** the parent still needs repository evidence
- **THEN** the platform records the real unsupported/failed outcome
- **AND** direct reading remains available
- **AND** no successful child execution is fabricated

### Requirement: Context-delegation evidence is bounded and semantically truthful

The platform SHALL retain enough local observation evidence to evaluate context delegation without creating a separate transcript or telemetry service. At minimum, supported observations SHALL distinguish source payload volume, returned payload volume, attributable direct re-read volume when observable, elapsed time, outcome, and provider/model provenance when truthfully known.

#### Scenario: Runtime does not expose exact token usage

- **GIVEN** a context delegation completed and source/result byte volumes are known
- **BUT** the runtime does not expose an exact supported token field
- **WHEN** the observation is recorded
- **THEN** byte/line payload evidence is retained separately
- **AND** token usage remains unknown rather than estimated as canonical usage

### Requirement: Initial context delegation remains soft before calibration

The first production context-delegation capability SHALL remain advisory and SHALL NOT hard-block ordinary repository Read operations. Hard interception or redirection of eligible reads requires a later evidence-gated change.

#### Scenario: Soft dogfood phase is active

- **GIVEN** context delegation is available during the initial dogfood phase
- **WHEN** the parent chooses a direct repository read
- **THEN** the platform does not block the read solely because a context worker exists
- **AND** later calibration may evaluate whether stronger enforcement is justified

### Requirement: Snapshot semantic extraction prefers routine read-only workers

Snapshot construction SHALL use deterministic preprocessing first and routine/read-only workers for bounded semantic extraction before stronger-model escalation, unless conflict, low confidence, or materially complex interpretation requires escalation.

#### Scenario: Bounded extraction is routine
- **WHEN** selected evidence can be summarized into a projection without a novel design decision
- **THEN** the platform may delegate that extraction through the existing routine read-only context-worker path
- **AND** the worker has no repository write authority

#### Scenario: Extraction is ambiguous or conflicting
- **WHEN** the routine worker reports materially low confidence or conflicting evidence that source-of-truth rules cannot resolve mechanically
- **THEN** the result is marked for stronger review/escalation
- **AND** the routine worker does not invent a new architecture decision

### Requirement: Snapshot worker evidence reuses routing provenance where practical

The platform SHALL avoid a parallel telemetry system solely for snapshot workers.

#### Scenario: Worker execution is measurable
- **WHEN** existing routing/context-worker provenance exposes timing or supported usage evidence
- **THEN** snapshot reporting may reference/reuse that evidence
- **AND** unavailable token fields remain unknown rather than guessed

### Requirement: Routing enforcement is bound to durable exact managed identity

For a managed task whose policy requires a routing decision/execution outcome, the platform SHALL bind archive and terminal routing enforcement to the exact durable managed task/change identity rather than only to a currently materialized active OpenSpec directory.

#### Scenario: Managed task reaches archive without routing evidence

- **GIVEN** an exact managed task requires routing evidence
- **AND** no valid route/execution outcome is durably recorded for that task
- **WHEN** the task attempts the managed archive boundary
- **THEN** archive is refused before the OpenSpec change is moved
- **AND** the diagnostic identifies the missing routing evidence and required sequencing.

#### Scenario: Routed task is archived before finish

- **GIVEN** a managed task has valid required routing/execution evidence
- **AND** its OpenSpec change is archived through the normal lifecycle
- **WHEN** terminal finish verifies the routing gate
- **THEN** the platform resolves the exact archived managed identity
- **AND** verifies the existing durable routing evidence for that identity
- **AND** does not silently pass merely because no active change directory exists.

#### Scenario: Another managed change is active

- **GIVEN** the exact task being finished is already archived
- **AND** another unrelated managed OpenSpec change is currently active
- **WHEN** terminal routing enforcement resolves provenance
- **THEN** it binds only to the archived task being finished
- **AND** SHALL NOT use the unrelated active change or its routing record.

#### Scenario: Routing is attempted after archive

- **GIVEN** a managed task has already crossed the archive boundary without a valid pre-implementation route
- **WHEN** a caller attempts `route-codex` or `route-claude`
- **THEN** route preparation remains rejected as out of sequence
- **AND** the platform SHALL NOT create a retrospective routing decision to legalize completed work.

### Requirement: Archived routing provenance remains truthfully readable

Routing and friction provenance readers SHALL be able to resolve previously recorded route/execution identity for an archived managed task when an exact durable binding exists. They SHALL reuse the existing routing record and SHALL NOT infer provider, model, participant, or outcome fields from unrelated active work.

Unavailable fields SHALL remain unknown.

#### Scenario: Friction is recorded after archive

- **GIVEN** a managed task was routed before implementation and later archived
- **AND** its durable routing record contains participant provenance
- **WHEN** a bounded post-archive friction record requests task provenance
- **THEN** the reader binds to that archived task/change
- **AND** preserves the truthfully recorded participant/provider/model fields
- **AND** does not require rematerializing the OpenSpec change.

### Requirement: Supported retained execution is explicit

When current routing policy permits the parent/current strong session to retain implementation work without a launched child executor, a successful retained path SHALL be represented as an explicit durable outcome on the existing routing record, bound to the exact managed task and carrying the required truthful postcheck/containment evidence.

Absence of a child launch alone SHALL NOT imply retained success.

#### Scenario: Parent retains supported work

- **GIVEN** current routing policy permits the selected work to remain on the parent/current strong session
- **WHEN** implementation completes without a child launch
- **THEN** a truthful retained outcome is persisted for the exact task
- **AND** the terminal routing gate verifies that outcome under the same exact-task contract.

#### Scenario: Unrecorded retention reaches completion

- **GIVEN** a routine/standard route has no successful child execution
- **AND** no explicit policy-valid retained outcome is recorded
- **WHEN** archive or terminal completion checks routing
- **THEN** the gate fails closed
- **AND** SHALL NOT treat missing execution evidence as implicit success.

### Requirement: Verified concurrent integration advancement is distinct from a delegated escape

The platform SHALL retain raw observation of integration `HEAD` movement during a delegated write, but it MAY classify a pure head movement as a verified concurrent integration advance rather than a containment violation only when the qualifying conditions for a verified concurrent integration advance hold. The routing execution receipt SHALL preserve the before/after heads and explicit classification.

#### Scenario: Another lifecycle fast-forwards clean integration during a native child run

- **GIVEN** a native hard-contained delegated writer runs in its assigned
  worktree
- **AND** the integration snapshot has no new, changed or disappeared paths
- **AND** a separate lifecycle fast-forwards integration from the pre-run head
  to the exact recorded remote-tracking base-branch head
- **WHEN** the delegated writer returns successfully
- **THEN** the execution records a verified concurrent integration advance
- **AND** the routing outcome is not marked as a delegated escape

#### Scenario: Head movement cannot be proven as a concurrent remote fast-forward

- **GIVEN** a delegated writer observes integration-head movement
- **WHEN** a path changed, the move is not a fast-forward, the remote ref does
  not exactly match, or containment is neither native hard nor detection-only
  verified under "Detection-only delegated writers accept a recorded integration advance"
- **THEN** the containment result remains failed
- **AND** normal friction recording remains available for the violation

### Requirement: Historic external-advance recovery is evidence-bound

The platform SHALL provide a recovery path for a historic delegated execution that was recorded failed solely because of a pure integration-head movement.

#### Scenario: A recorded pure-head-move false positive is reviewed

- **GIVEN** an existing route records a launched native child with successful
  return code but a containment failure
- **AND** the supplied friction event binds to that exact task, execution and
  a verified pure remote fast-forward with no path mutation
- **WHEN** an operator invokes the narrow recovery command
- **THEN** the route records the reviewed recovery and retains the original
  execution evidence
- **AND** terminal routing verification can use that explicit recovery record

#### Scenario: Historic evidence is incomplete or mismatched

- **WHEN** the supplied event, route identity, head facts, native enforcement
  evidence or path-mutation facts cannot be verified exactly
- **THEN** recovery refuses without changing routing evidence

#### Scenario: The recorded external advance is no longer the current remote tip

- **GIVEN** `after_head` was a verified concurrent advance at the time of the
  incident but the checkout's remote-tracking main has since advanced further
  (including through an unrelated later merge)
- **AND** the checkout's own remote-tracking ref reflog still records
  `after_head` as its value at a timestamp inside the flagged route's own
  recorded execution window
- **WHEN** an operator invokes the narrow recovery command
- **THEN** recovery succeeds using the dedicated historical verifier
- **AND** the live containment postcheck's own current-tip verifier is not
  consulted for this decision

#### Scenario: Ancestry to current main is not durable temporal proof

- **GIVEN** `after_head` is an ancestor of the checkout's current
  remote-tracking main
- **AND** no durable local record binds `after_head` to that ref at a
  timestamp within the flagged route's recorded execution window
- **WHEN** an operator invokes the narrow recovery command
- **THEN** recovery refuses without changing routing evidence
- **AND** the refusal is not bypassable by a force/override flag

#### Scenario: A successful recovery reaches the durable routing record

- **GIVEN** every recovery fact has been proven
- **WHEN** the recovery command writes its result
- **THEN** the durable integration-root routing record for that exact task
  carries the identical recovered execution and recovery evidence as the
  task-local copy
- **AND** a terminal routing or archive gate reading the durable record
  accepts the recovered classification

#### Scenario: Durable persistence fails during recovery

- **GIVEN** every recovery fact has been proven
- **WHEN** writing the durable integration-root routing record fails
- **THEN** recovery refuses without writing the task-local copy either
- **AND** no terminal gate can observe a recovered task-local record while
  the durable record remains stale

### Requirement: Self-reported delegated execution is not hard launch proof

The platform SHALL NOT treat a value it cannot independently verify, such as a supervisor-supplied Claude agent identifier, as proof that a delegated executor launched. Such execution SHALL be recorded as an explicit claimed/unverified outcome whose launch state is unknown.

#### Scenario: Arbitrary agent identifier is recorded

- **GIVEN** a routine or standard Claude route
- **WHEN** a caller records execution with an arbitrary non-empty agent identifier
- **THEN** the record's outcome is claimed with self-reported launch evidence and unknown launch state
- **AND** no executed participant is attached
- **AND** reports classify it as claimed, not launched

#### Scenario: Legacy self-reported launch record reaches the gate

- **GIVEN** an older Claude routing record marks `launched: true` from a supplied agent identifier without the claimed outcome
- **WHEN** the terminal routing gate runs
- **THEN** it refuses the record as unverifiable launch evidence
- **AND** directs the supervisor to re-record the claimed execution

#### Scenario: Platform-observed Codex launch

- **GIVEN** the platform-owned Codex launcher observed a real subprocess run
- **WHEN** the routing gate and reports read that record
- **THEN** its launch evidence and outcome semantics are unchanged

### Requirement: Large observations can become cold while exact evidence remains recallable

Dev Platform SHALL support a provider-neutral lifecycle for eligible large tool/runtime observations in which the exact original payload is preserved for the supported run/session lifetime and the active context MAY replace that payload with a bounded reference. The bounded reference SHALL identify the original through a stable handle and SHALL NOT become a semantic replacement for the exact evidence.

#### Scenario: Large observation is cooled

- **GIVEN** a supported runtime returns an eligible large observation
- **WHEN** the observation lifecycle cools that result
- **THEN** the exact original payload remains recoverable
- **AND** the active representation contains a stable handle plus bounded metadata/excerpt
- **AND** later turns do not require the full original payload to remain hot by default

#### Scenario: Small observation does not need cooling

- **GIVEN** a returned observation is below the configured/evidenced eligibility boundary
- **WHEN** the observation lifecycle evaluates it
- **THEN** the existing direct representation remains usable
- **AND** no unnecessary archive/recall ceremony is required

#### Scenario: Cooling is unsupported or fails

- **GIVEN** the current runtime cannot safely provide the observation lifecycle or preservation fails
- **WHEN** the result would otherwise be cooled
- **THEN** the platform keeps or restores the current full-evidence path
- **AND** does not claim that the observation was safely archived

### Requirement: Cold observations support exact targeted recall

A cold observation SHALL support exact bounded recall against the preserved original. Recall SHALL allow the caller to retrieve a requested range or other deterministic bounded subset without reinjecting the entire original by default.

#### Scenario: Agent needs one exact failure region

- **GIVEN** a cold observation has a valid handle
- **AND** later reasoning needs one bounded exact region
- **WHEN** targeted recall is requested
- **THEN** the returned content matches the preserved original exactly for that requested region
- **AND** unrelated portions are not returned by default

#### Scenario: Handle is stale or unknown

- **WHEN** recall references a handle that cannot be resolved in the current supported lifetime
- **THEN** the platform reports the missing/stale evidence explicitly
- **AND** does not fabricate recalled content

### Requirement: Observation-efficiency evidence remains truthful and bounded

The platform SHALL reuse existing execution-efficiency provenance for observation lifecycle evidence rather than create a parallel transcript store. Deterministic payload fields MAY include source bytes/lines, hot bytes/lines, recall bytes/lines, trigger count/rate and trigger intensity. Token/cache/request fields SHALL be populated only from authoritative supported runtime evidence; deterministic payload reduction SHALL NOT be labelled as measured token savings.

#### Scenario: Runtime exposes no canonical token breakdown

- **GIVEN** deterministic source and hot payload sizes are known
- **BUT** the runtime exposes no supported exact token/cache usage
- **WHEN** observation evidence is recorded
- **THEN** payload reduction is retained as deterministic evidence
- **AND** token/cache savings remain unknown rather than inferred

### Requirement: Execution logs may be reduced only while exact source evidence remains authoritative

After the large-observation lifecycle preserves an eligible execution log, Dev Platform MAY derive a compact structured receipt for active-context use. The original log and canonical command/result evidence SHALL remain authoritative, and a reducer receipt SHALL NOT replace test, CI or completion pass/fail semantics.

Known deterministic fields SHOULD be parsed directly when practical before model-based semantic reduction is used.

#### Scenario: Noisy failing log is reduced

- **GIVEN** an eligible execution log is preserved as an exact cold observation
- **WHEN** a supported reducer creates a compact receipt
- **THEN** the receipt references the preserved source identity
- **AND** retains the bounded failure facts/evidence needed for navigation
- **AND** the original remains exactly recallable
- **AND** canonical command/check outcome remains owned by the source execution

#### Scenario: Deterministic log structure already exposes the fact

- **GIVEN** a supported log format exposes exit status or another required field deterministically
- **WHEN** the receipt is built
- **THEN** the platform uses the deterministic field as its source
- **AND** does not require a model to reinterpret that field merely for consistency
- **AND** an exact bounded log line MAY form a receipt without model output when its receipt is smaller than the existing hot representation

### Requirement: Reducer receipts require deterministic evidence binding

A semantic reducer receipt SHALL be trusted only to the extent that its evidence-bearing claims can be bound back to the preserved source.

#### Scenario: Reducer invents an error quote

- **GIVEN** a receipt contains a quote or range not present at the claimed source location
- **WHEN** receipt verification runs
- **THEN** the receipt is rejected as unverified
- **AND** the caller can use the preserved exact source
- **AND** no verification success is derived from the fabricated receipt

#### Scenario: Reducer reports a result inconsistent with canonical exit evidence

- **GIVEN** canonical command evidence records a failing exit status
- **BUT** the receipt claims the command passed
- **WHEN** receipt verification runs
- **THEN** the receipt is rejected
- **AND** canonical execution evidence remains authoritative

### Requirement: Reducer-efficiency evidence reuses execution provenance

Reducer execution SHALL reuse bounded routing/execution provenance where practical. The platform MAY record reducer profile/participant, source and receipt volume, reducer verification outcome, fallback/recall volume and exact supported runtime usage. It SHALL NOT create a transcript warehouse or infer canonical token savings from byte/line reduction.

#### Scenario: Routine reducer is unavailable

- **WHEN** the configured reducer cannot run safely in the current runtime
- **THEN** the exact source path remains available
- **AND** provenance records the actual fallback rather than a successful reducer execution

### Requirement: Concrete model bindings change as policy only

Concrete provider-local model bindings SHALL be changed only in the replaceable routing policy (`[model_routing]` and its template and built-in default mirror) and SHALL NOT alter routing tiers, assurance, verification policy, the routing/execution provenance schema or the lifecycle.

#### Scenario: A newer stable model replaces a superseded binding

- **GIVEN** a superseded model is bound to a tier
- **WHEN** a newer stable model is adopted for that tier
- **THEN** only the policy value changes
- **AND** the authored start tier, assurance and verification requirements of every task are unchanged

#### Scenario: A regression requires rollback

- **GIVEN** a new binding shows a regression in recorded calibration evidence
- **WHEN** the previous binding is restored and released
- **THEN** managed projects return to it through the normal template update without per-project edits

### Requirement: Execution path is fixed before task-content mutation

For a managed R2/R3 task, route preparation SHALL record an explicit execution plan before the first task-content change: either a delegated child executor, or supervisor-retained execution with its policy reason.

#### Scenario: Default routine/standard route is supervisor-retained

- **WHEN** a routine/standard route on a linked worktree is prepared without an explicit delegation request
- **THEN** the routing record carries a supervisor-retained plan with policy `balanced-parent` and a task-content pre-snapshot
- **AND** the supervisor finalizes it with the retained outcome after implementation

#### Scenario: Policy requires a child executor

- **WHEN** a routine/standard route on a linked worktree is prepared with an explicit delegation request, including Codex dispatch
- **THEN** the routing record carries a delegated-child plan with a task-content pre-snapshot
- **AND** the authored start tier and the later actual executor remain separate recorded facts

#### Scenario: Policy permits supervisor execution

- **WHEN** a complex route, or a routine/standard route on a parent-only topology, is prepared
- **THEN** the routing record carries a supervisor-retained plan with the policy reason
- **AND** no child launch or escalation is recorded

#### Scenario: Content already diverged at routing

- **WHEN** task content outside the managed package has already changed before routing
- **THEN** route preparation fails naming the diverged paths
- **AND** no route is recorded

### Requirement: A required child executor needs an open delegation before content changes

When the plan is a delegated child, the platform SHALL require an open delegation record before task content changes.

#### Scenario: Correct delegated path

- **GIVEN** a delegated-child plan
- **WHEN** the supervisor opens the delegation, the child changes task content and the execution is recorded
- **THEN** early and archive routing gates pass with a claimed, self-reported execution and no verified-launch claim

#### Scenario: Execution recorded after the fact

- **GIVEN** a delegated-child plan with no open delegation and changed task content
- **WHEN** a Claude execution is recorded
- **THEN** recording is refused naming the missing delegation step

#### Scenario: Delegation opened late

- **GIVEN** a delegated-child plan whose task content has already diverged from the pre-snapshot
- **WHEN** a delegation is opened
- **THEN** it is refused

### Requirement: Routing mismatch fails at routing-adjacent lifecycle commands

The platform SHALL fail closed, through a shared read-only early gate, when a delegated-child plan has no open or completed delegation and task content differs from the pre-snapshot.

#### Scenario: Supervisor implements under a child-executor plan

- **GIVEN** a delegated-child plan with no open delegation
- **WHEN** the supervisor writes implementation content and runs status or a check entrypoint
- **THEN** the command fails before expensive checks, naming the diverged paths and the required delegation step

#### Scenario: First supervisor write under a child-executor plan

- **GIVEN** a delegated-child plan with no open delegation
- **WHEN** the supervisor attempts its first implementation file write through the agent write tool
- **THEN** the write is denied before the file changes
- **AND** the denial names the delegation step to run first

#### Scenario: First write before routing

- **GIVEN** an active managed task with no recorded route
- **WHEN** the supervisor attempts an implementation file write
- **THEN** the write is denied naming the routing command to run first

#### Scenario: Legitimate writes pass the write gate

- **GIVEN** a supervisor-retained plan, or a delegated-child plan with an open delegation
- **WHEN** an implementation file is written
- **THEN** the write gate allows it with no additional step

#### Scenario: Supervisor-retained plan is unaffected

- **GIVEN** a supervisor-retained plan declared at route time
- **WHEN** the supervisor changes task content and runs the same commands
- **THEN** the early gate passes

#### Scenario: Plan-less active record

- **GIVEN** an active managed route without a plan and without execution
- **WHEN** the early gate runs
- **THEN** it fails with a re-route diagnostic

### Requirement: Retained execution is declared up front and recovery never fabricates evidence

Recording a retained outcome SHALL require a supervisor-retained plan declared at route time, or recorded through an explicit owner-approved retention, and SHALL only finalize it with the containment postcheck.

#### Scenario: Retained outcome after up-front plan

- **GIVEN** a supervisor-retained plan
- **WHEN** implementation completes and the retained outcome is recorded
- **THEN** the record is a real retained execution with a clean postcheck and the terminal gate passes

#### Scenario: Late switch to retention

- **GIVEN** a delegated-child plan with diverged task content and no delegation
- **WHEN** a retained outcome or escalation to retention is attempted
- **THEN** the operation is refused and names the explicit owner-approved retention as the only way to record the owner's decision

#### Scenario: Escalation after a real delegation

- **GIVEN** a recorded real delegation whose result was reviewed
- **WHEN** a recorded escalation with a concrete reason switches the plan to retention
- **THEN** the escalation is accepted and provenance keeps the delegation and the escalation distinct

#### Scenario: Unlaunched Codex attempt

- **WHEN** Codex is refused or fails before its child process starts
- **THEN** the attempt is closed with outcome not-launched and no open delegation remains
- **AND** subsequent supervisor writes fail the early gate and cannot authorize retention or escalation without an explicit owner-approved retention

#### Scenario: Lifecycle rename hides a source deletion

- **WHEN** a tracked implementation path is moved into an excluded lifecycle directory
- **THEN** divergence includes the source path for both staged and committed changes
- **AND** routing, late delegation and escalation cannot bypass the unchanged-content requirement

#### Scenario: Recovery preserves child safety and outcome

- **GIVEN** a failed child execution
- **WHEN** re-routing, escalation or retained finalization is requested
- **THEN** unresolved containment violations and unreleased or ambiguous Codex writers block the request
- **AND** retained finalization after an accepted escalation preserves the prior child execution, delegation and escalation as distinct provenance

#### Scenario: Fresh source checkout runs checks

- **GIVEN** committed managed package metadata without local managed task state
- **WHEN** the check/test entrypoint runs in a fresh source checkout
- **THEN** checks remain available without resolving private executor lineage

#### Scenario: Recovery without a saved execution receipt

- **GIVEN** an existing route whose child escaped its containment boundary before an execution receipt was saved
- **WHEN** re-routing is requested
- **THEN** the original containment boundary is checked and the violation blocks recovery

#### Scenario: Failed child retry retains provenance

- **WHEN** an attributable failed Codex child is re-routed
- **THEN** the complete prior route including executor identity, execution and escalation history remains in retry provenance and subsequent durable records

### Requirement: An owner-approved supervisor-written diff can be retained explicitly

The platform SHALL provide one explicit routing command that, on the owner's explicit decision, switches a delegated-child plan with no recorded delegation, no execution other than a closed child attempt that never launched, and task content diverged from the pre-snapshot to a supervisor-retained plan with policy owner-approved.

#### Scenario: Owner approves a supervisor-written diff

- **GIVEN** a delegated-child plan with no delegation and diverged task content
- **WHEN** the owner-approved retention is recorded with the owner's statement and a reason
- **THEN** the plan becomes supervisor-retained with policy owner-approved and the recorded approval
- **AND** the early gate passes, the retained execution records the approval and the archive gate passes

#### Scenario: Approval refused

- **WHEN** the approval or reason is empty, the plan is already retained, a real delegation or an execution other than a never-launched attempt exists, or task content is unchanged
- **THEN** the command fails naming the reason and the routing record is unchanged

#### Scenario: Approval after a never-launched child attempt

- **GIVEN** a delegated-child plan whose only recorded execution is a closed child attempt that never launched, and diverged task content
- **WHEN** the owner-approved retention is recorded and finalized
- **THEN** the plan becomes supervisor-retained with policy owner-approved and the retained execution keeps the attempt as prior execution

#### Scenario: Forged policy

- **WHEN** a routing record claims the owner-approved policy without a complete recorded approval
- **THEN** reading the record fails plan validation

### Requirement: Detection-only delegated writers accept a recorded integration advance

Every platform fast-forward of the integration checkout's main branch SHALL append an integration-advance receipt naming before and after heads, the recorded remote-tracking main, the acting worktree, tool and time.

#### Scenario: Sibling merge during a Claude delegation

- **GIVEN** a Claude delegation is open
- **AND** another task's finish fast-forwards integration main to the recorded remote-tracking main and writes a receipt
- **WHEN** the supervisor records the execution
- **THEN** the execution is recorded with a verified concurrent advance and the raw head movement

#### Scenario: Unproven movement

- **WHEN** a path changed, the move is not a fast-forward, the head differs from remote-tracking main, a receipt is missing or the chain names the delegated worktree
- **THEN** recording fails as a containment violation

#### Scenario: Historical false violation

- **GIVEN** a Claude delegation failed recording because of a pure head move before receipts existed
- **WHEN** recovery is requested with the exact friction event, heads proven by the remote-tracking reflog within the delegation window and the owner's explicit risk acceptance
- **THEN** an owner-authorized historical recovery record, not marked verified, is stored without creating an execution
- **AND** the later execution keeps that recovery apart from any verified advance
- **AND** later recording classifies any further movement only through receipts

#### Scenario: Historical recovery without owner risk acceptance

- **WHEN** recovery is requested without the owner's explicit risk acceptance
- **THEN** it is refused and nothing is written

#### Scenario: Receipted parallel merge needs no owner input

- **GIVEN** a Claude delegation is open
- **WHEN** another lifecycle fast-forwards integration main and writes a receipt
- **THEN** the execution is recorded with a verified concurrent advance without any recovery or owner approval

### Requirement: Sandboxed Claude delegation is platform-observed execution

The platform SHALL provide an explicit sandboxed Claude dispatch for a prepared `delegated-child` Claude route.

#### Scenario: Sandboxed Claude child completes
- **GIVEN** a prepared standard Claude route with unchanged task content
- **WHEN** the sandboxed Claude dispatch runs and the writer exits successfully with a valid result
- **THEN** the routing record has a closed platform-observed delegation and an execution with `launched: true`, mechanism `sandbox-runtime` and an executed participant
- **AND** the terminal routing gate accepts it

#### Scenario: Native hand-off unchanged
- **WHEN** the supervisor uses the native Agent-tool hand-off
- **THEN** the execution is still recorded as a self-reported claim with no executed participant

#### Scenario: Unsupported platform
- **WHEN** the sandboxed Claude dispatch is requested outside macOS
- **THEN** no process starts, a closed not-launched attempt is recorded and no hard containment is claimed

### Requirement: A task in the main copy of a project can record its retained outcome after implementation

For a supervisor-retained route in the `standalone-clone` topology with no delegated child, the containment postcheck SHALL accept implementation commits made after route preparation, so the retained outcome can be recorded, the change archived and published. A commit that is unrelated to the task is not detectable in this topology, because the supervisor is its only writer; review of the published PR is the guard for that.

#### Scenario: Implementation commits in the main copy
- **GIVEN** a standalone-clone route prepared at HEAD H with a retained plan
- **WHEN** the supervisor commits the implementation and records the retained outcome
- **THEN** the outcome is recorded with the commits as `task_commits`
- **AND** the change can be archived and published

#### Scenario: Leftover or foreign change in the main copy
- **WHEN** the working tree has an uncommitted or untracked path, a changed pre-existing dirty path, or HEAD moved to a commit that is not a descendant of the snapshot HEAD
- **THEN** recording the retained outcome fails with a containment violation naming it

#### Scenario: Rendered project hints
- **WHEN** a routing gate or error suggests a recovery command
- **THEN** every command it names exists in the rendered project

#### Scenario: Task state is not committed
- **WHEN** a managed task writes `.managed-task-state.json` in a project that does not ignore it
- **THEN** the file is ignored locally by the repository's exclude file and does not appear as untracked

### Requirement: Concrete execution profile bindings live in versioned configuration

Concrete runtime model IDs and reasoning-effort settings SHALL live in versioned platform/runtime configuration or generated agent profiles rather than durable task artifacts.

#### Scenario: Execution profile is resolved to a concrete model

- **WHEN** an execution profile is resolved to a concrete runtime model ID and reasoning-effort setting
- **THEN** the values come from versioned platform/runtime configuration or generated agent profiles
- **AND** they are not stored in durable task artifacts

### Requirement: A strong parent is not a mandatory routing entrypoint

Provider-local delegation, including a strong parent/supervisor, remains a supported execution capability, but a strong parent SHALL NOT be a mandatory entrypoint for every routing-enabled managed task: execution MAY begin directly on the tier-recommended executor. If work starts on a stronger-than-recommended session, the platform MAY down-route through the existing supported provider-local child path instead of requiring ceremonial re-delegation.

#### Scenario: Execution begins on the tier-recommended executor

- **WHEN** a routing-enabled managed task starts
- **THEN** execution may begin directly on the tier-recommended executor without a strong parent entrypoint

#### Scenario: Work starts on a stronger-than-recommended session

- **WHEN** work starts on a session stronger than the recommended tier
- **THEN** the platform may down-route through the existing supported provider-local child path
- **AND** ceremonial re-delegation is not required

### Requirement: The supervisor implements routed work itself by default

By default the supervisor SHALL implement routine/standard and complex work itself; delegating routine/standard implementation to a child executor SHALL happen only on an explicit delegation request.

#### Scenario: No explicit delegation request

- **WHEN** routine/standard or complex work is routed and no explicit delegation request exists
- **THEN** the supervisor implements the work itself

#### Scenario: Explicit delegation request

- **WHEN** an explicit delegation request exists for routine/standard implementation
- **THEN** that implementation may be delegated to a child executor

### Requirement: Native containment is not wrapped in a redundant prevention layer

Native containment SHALL NOT be wrapped in an additional provider-specific prevention layer merely because a legacy guard exists.

#### Scenario: Native containment is available

- **WHEN** native containment protects a routed writer
- **THEN** no additional provider-specific prevention layer is wrapped around it merely because a legacy guard exists

### Requirement: Custom guarded launch is limited to unprovable native isolation

A custom guarded launch or detection-only fallback SHALL be used only where native isolation is unavailable, insufficient, or not provable for the supported runtime/mode.

#### Scenario: Native isolation cannot be proven

- **WHEN** native isolation is unavailable, insufficient, or not provable for the supported runtime/mode
- **THEN** a custom guarded launch or detection-only fallback may be used

#### Scenario: Native isolation is proven

- **WHEN** native isolation is proven for the supported runtime/mode
- **THEN** no custom guarded launch or detection-only fallback is used

### Requirement: Routed writers keep a content-aware integration post-check

A lightweight content-aware integration post-check SHALL remain defense in depth for routed writers.

#### Scenario: Routed writer finishes

- **WHEN** a routed writer finishes
- **THEN** a lightweight content-aware integration post-check still runs as defense in depth

### Requirement: Delegated executors escalate when the selected profile is insufficient

A delegated executor SHALL stop and escalate whenever evidence shows that the selected execution profile is insufficient. Escalation triggers SHALL include at least a newly discovered frontier hard trigger, material OpenSpec/current-spec conflict, substantial unexpected scope growth, unexpected cross-cutting impact, materially low confidence, or repeated substantive failure to satisfy required verification after reasonable bounded attempts.

#### Scenario: Evidence shows the profile is insufficient

- **WHEN** a delegated executor finds evidence such as a newly discovered frontier hard trigger or a material OpenSpec/current-spec conflict
- **THEN** it stops and escalates

### Requirement: Escalation preserves useful task state

Escalation SHALL preserve useful task state: canonical OpenSpec, current assigned worktree/diff, relevant findings and verification failures, plus the reason for escalation. Escalation SHALL NOT restart the task from scratch without a concrete need. Downgrade below the authored tier is not required by this version.

#### Scenario: Executor escalates

- **WHEN** a delegated executor escalates
- **THEN** canonical OpenSpec, the current assigned worktree/diff, relevant findings and verification failures and the reason for escalation are preserved
- **AND** the task is not restarted from scratch without a concrete need

### Requirement: Model routing does not bypass the completion lifecycle

Model routing SHALL NOT bypass OpenSpec consistency, project checks, semantic verification, protected-main requirements or publication rules. The parent/supervisor remains responsible for assessing the delegated result before the normal completion lifecycle proceeds.

#### Scenario: Routed task completes

- **WHEN** a routed task proceeds to completion
- **THEN** OpenSpec consistency, project checks, semantic verification, protected-main requirements and publication rules still apply
- **AND** the parent/supervisor assesses the delegated result before the normal completion lifecycle proceeds

### Requirement: Backlog Issue title exposes the recommended start tier

The human-facing Development Backlog Issue title SHALL expose the recommendation as a compact abstract prefix so the user can select the intended starting capability without opening the Issue.

#### Scenario: Managed Issue is shown in the backlog

- **WHEN** a managed task has a recorded recommended start tier
- **THEN** the Development Backlog Issue title carries it as a compact abstract prefix

### Requirement: Concrete model IDs stay out of durable routing artifacts

Concrete model IDs SHALL NOT be embedded in the durable Issue/OpenSpec solely for routing and SHALL remain governed by current versioned runtime/platform mapping.

#### Scenario: Recommendation is recorded

- **WHEN** the recommended start tier is recorded in the durable Issue/OpenSpec
- **THEN** no concrete model ID is embedded solely for routing
- **AND** concrete models remain governed by current versioned runtime/platform mapping

### Requirement: Production policy recommends R2 and R3

The first production policy SHALL support `R2` balanced and `R3` frontier recommendations.

#### Scenario: Production recommendation

- **WHEN** a production start tier is recommended
- **THEN** `R2` balanced and `R3` frontier are supported recommendations

### Requirement: R1 economy is reserved until evidence-gated enablement

`R1` economy MAY be represented as a reserved tier but SHALL NOT be recommended for production work until a later accepted evidence-gated change enables it.

#### Scenario: R1 is considered for production work

- **WHEN** a production task would be recommended `R1`
- **THEN** `R1` is not recommended until a later accepted evidence-gated change enables it
- **AND** `R1` may still be represented as a reserved tier

### Requirement: Selecting R3 requires outcome-changing evidence

Selecting `R3` SHALL require evidence that additional reasoning capability is plausibly outcome-changing, such as unresolved architecture, materially unknown diagnosis, weak verification combined with high consequence, novel cross-system interaction without an established pattern, trustworthy history of comparable R2 escalation, or a prior substantive balanced failure for reasoning/diagnostic causes.

#### Scenario: R3 is selected

- **WHEN** `R3` is selected for a task
- **THEN** evidence shows that additional reasoning capability is plausibly outcome-changing, such as unresolved architecture or a prior substantive balanced failure for reasoning/diagnostic causes

### Requirement: Size and blast radius alone do not require R3

Expected diff size, number of files, public visibility, blast radius or failure cost SHALL NOT by themselves require `R3`. The platform MAY increase reasoning effort or assurance while retaining `R2`.

#### Scenario: Large or visible task without a trigger

- **WHEN** a task has a large expected diff, many files, public visibility, large blast radius or high failure cost but no frontier trigger
- **THEN** `R3` is not required by those facts alone
- **AND** the platform may increase reasoning effort or assurance while retaining `R2`

### Requirement: Execution provenance distinguishes selected and confirmed values

For each participant where the information is applicable and available, provenance SHOULD represent the runtime/provider, participant role, execution profile, model identity, reasoning effort, bounded execution identifier and parent/child relationship. Model and reasoning-effort fields SHALL carry enough source/status information to distinguish platform-selected/configured values from runtime-confirmed values and unknown values.

#### Scenario: Participant provenance is recorded

- **WHEN** provenance is recorded for a participant where the information is applicable and available
- **THEN** it represents runtime/provider, role, execution profile, model identity, reasoning effort, bounded execution identifier and parent/child relationship
- **AND** model and reasoning-effort fields distinguish platform-selected/configured, runtime-confirmed and unknown values

### Requirement: Model self-identification is not authoritative provenance

Free-form model self-identification SHALL NOT be the authoritative source for model or effort provenance.

#### Scenario: Model reports its own identity

- **WHEN** a model identifies itself in free-form text
- **THEN** that self-identification is not used as the authoritative source for model or effort provenance

### Requirement: Prepared routes are not recorded as executed children

A route that was merely prepared SHALL NOT be represented as an executed child.

#### Scenario: Route prepared but not run

- **WHEN** a route was merely prepared
- **THEN** it is not represented as an executed child

### Requirement: Fallback and escalation provenance records the actual path

Fallback and escalation SHALL preserve the actual execution path rather than the preferred path that failed to run.

#### Scenario: Preferred path failed to run

- **WHEN** a fallback or escalation occurred
- **THEN** provenance records the actual execution path rather than the preferred path that failed to run

### Requirement: Provenance runtime adapters are verified at preflight

The concrete runtime adapters SHALL be verified against the supported Codex and Claude Code surfaces at implementation preflight.

#### Scenario: Implementing a runtime adapter

- **WHEN** a concrete runtime provenance adapter is implemented
- **THEN** it is verified against the supported Codex and Claude Code surfaces at implementation preflight

### Requirement: Unexposed provenance fields degrade truthfully

If a runtime does not reliably expose a desired field, the platform SHALL degrade truthfully by recording that field as unknown or only as selected/configured; it SHALL NOT scrape unstable UI text or infer effective execution state from an unsupported assumption solely to make the record complete.

#### Scenario: Runtime does not expose a field

- **WHEN** a runtime does not reliably expose a desired provenance field
- **THEN** the field is recorded as unknown or only as selected/configured
- **AND** unstable UI text is not scraped and effective execution state is not inferred from an unsupported assumption

### Requirement: Model lineup changes do not require editing historical artifacts

Historical provenance MAY preserve the model/runtime values that actually or reportedly applied to that execution, but a later change to the supported model lineup SHALL NOT require editing old Development Backlog Issues or accepted OpenSpec requirements solely to rename current executor models.

#### Scenario: Supported model lineup changes

- **WHEN** the supported model lineup changes
- **THEN** old Development Backlog Issues and accepted OpenSpec requirements are not edited solely to rename current executor models
- **AND** historical provenance may keep the values that actually or reportedly applied to that execution

### Requirement: Execution timing is recorded from the platform boundary

The platform SHALL record execution timing from its own execution boundary.

#### Scenario: Managed execution runs

- **WHEN** non-trivial managed execution runs
- **THEN** the platform records execution timing from its own execution boundary

### Requirement: Optional usage measurements carry source and status

Runtime/provider-supplied usage fields such as input/prompt tokens, cache-read tokens, fresh/computed input tokens, output tokens, total tokens, and model-request/turn counts MAY be recorded when the supported runtime exposes authoritative values. Optional measurements SHALL preserve enough source/status information to distinguish measured/confirmed values from unavailable or unknown values.

#### Scenario: Runtime exposes usage

- **WHEN** the supported runtime exposes authoritative token or model-request/turn usage values
- **THEN** they may be recorded
- **AND** each optional measurement keeps source/status information distinguishing measured/confirmed from unavailable or unknown values

### Requirement: Missing efficiency evidence is neither zero nor a failure

Missing efficiency evidence SHALL NOT be represented as zero and SHALL NOT make an otherwise valid task execution fail solely because a provider does not expose a usage metric.

#### Scenario: Provider exposes no usage metric

- **WHEN** a provider does not expose a usage metric
- **THEN** the metric is not recorded as zero
- **AND** an otherwise valid task execution does not fail solely for that reason

### Requirement: Historical records without efficiency fields remain readable

Historical execution records that predate efficiency fields SHALL remain readable and SHALL be treated as missing evidence rather than invalid or zero-valued observations.

#### Scenario: Record predates efficiency fields

- **WHEN** a historical execution record predates efficiency fields
- **THEN** it remains readable
- **AND** it is treated as missing evidence rather than invalid or zero-valued observations

### Requirement: Cross-runtime model-request counts require shared semantic identity

The schema SHALL compare a model-request count across runtimes only when each contributing adapter has authoritative evidence that its counted event has that same semantic identity.

#### Scenario: Comparing model-request counts

- **WHEN** model-request counts from several runtimes are compared
- **THEN** they are compared only when each contributing adapter has authoritative evidence that its counted event has the same semantic identity

### Requirement: Runtime-local counters are not normalized into model-request counts

Runtime-local turn, assistant-message or step counters MAY be retained as bounded evidence but SHALL NOT be silently normalized into a cross-runtime model-request metric.

#### Scenario: Runtime-local counter is retained

- **WHEN** a runtime-local turn, assistant-message or step counter is retained
- **THEN** it is not silently normalized into a cross-runtime model-request metric

### Requirement: Historical ambiguous counters keep their original semantics

Historical ambiguous counters SHALL remain readable without being upgraded to stronger semantics.

#### Scenario: Ambiguous historical counter is read

- **WHEN** a historical ambiguous counter is read
- **THEN** it remains readable without being upgraded to stronger semantics

### Requirement: Calibration eligibility depends only on routing facts

Routing-calibration eligibility SHALL be based on the routing facts needed for the decision, independently from whether optional efficiency fields such as token usage or a cross-runtime request counter are comparable.

#### Scenario: Efficiency fields are not comparable

- **WHEN** a record has the routing facts needed for the decision but lacks comparable token usage or a cross-runtime request counter
- **THEN** it remains eligible for routing calibration

### Requirement: Calibration breakdowns carry their own sample counts

Breakdowns by task family, rubric version and provider/model generation SHALL include their own sample counts and SHALL NOT be presented as confident tuning evidence when the corresponding sample is insufficient.

#### Scenario: Breakdown sample is insufficient

- **WHEN** a breakdown by task family, rubric version or provider/model generation has an insufficient sample
- **THEN** it shows its own sample count
- **AND** it is not presented as confident tuning evidence

### Requirement: Context workers resolve through replaceable provider-local routing

The context worker SHALL resolve through replaceable provider-local routing configuration rather than durable concrete model IDs in task artifacts. Cross-provider context delegation SHALL NOT be required.

#### Scenario: Context worker is selected

- **WHEN** a context worker is selected
- **THEN** it resolves through replaceable provider-local routing configuration rather than durable concrete model IDs in task artifacts
- **AND** cross-provider context delegation is not required

### Requirement: Payload counts are not labelled as token usage

Deterministic line or byte counts MAY be used as payload-reduction evidence but SHALL NOT be labelled as measured token or request usage.

#### Scenario: Line counts are reported

- **WHEN** deterministic line or byte counts are reported for context delegation
- **THEN** they may serve as payload-reduction evidence
- **AND** they are not labelled as measured token or request usage

### Requirement: Canonical token fields come only from exact runtime evidence

Canonical token/request fields SHALL be populated only from exact supported runtime evidence; unavailable values remain unknown.

#### Scenario: Runtime gives no exact usage

- **WHEN** exact supported runtime evidence for token/request usage is unavailable
- **THEN** the canonical token/request fields remain unknown

### Requirement: Exact managed identity verifies routing after archive

The same exact identity SHALL be usable to verify the existing durable routing record after archive. Absence of an active change directory SHALL NOT by itself satisfy the routing gate for a known managed task.

#### Scenario: Change directory is archived

- **WHEN** a known managed task has no active change directory
- **THEN** the existing durable routing record is verified through the same exact identity
- **AND** the missing active change directory does not by itself satisfy the routing gate

### Requirement: Durable identity lookup does not enable post-archive routing

Durable identity lookup for verification/read purposes SHALL NOT make route preparation or dispatch valid after archive; pre-implementation routing remains an active-change operation.

#### Scenario: Route preparation after archive

- **WHEN** route preparation or dispatch is attempted after archive
- **THEN** durable identity lookup does not make it valid
- **AND** pre-implementation routing remains an active-change operation

### Requirement: Qualifying conditions for a verified concurrent integration advance

The qualifying conditions for a verified concurrent integration advance SHALL be that the writer had native hard containment or detection-only movement was verified under "Detection-only delegated writers accept a recorded integration advance", no integration path was created, changed or disappeared, the new head is a fast-forward descendant of the pre-run head, and it exactly equals the integration checkout's recorded remote-tracking base-branch ref.

#### Scenario: All qualifying conditions hold

- **WHEN** a pure integration head movement occurs during a delegated write with native hard containment, no integration path change, and a new head that is a fast-forward descendant of the pre-run head equal to the recorded remote-tracking base-branch ref
- **THEN** the qualifying conditions for a verified concurrent integration advance hold

### Requirement: Other integration head movement remains a containment violation

All other integration-head movement, including detection-only execution not verified under "Detection-only delegated writers accept a recorded integration advance", non-fast-forward movement, unverified/missing remote refs, or any path-level change, SHALL remain a containment violation.

#### Scenario: Non-fast-forward integration movement

- **WHEN** integration head movement is non-fast-forward, has unverified or missing remote refs, or includes a path-level change
- **THEN** it remains a containment violation

### Requirement: Historic external-advance recovery requires exact matching evidence

Recovery SHALL require an exact matching machine-local friction event and durable route identity, SHALL verify the recorded before/after and remote-fast-forward facts, and SHALL preserve the original execution outcome inside the recovery evidence. Recovery SHALL NOT act as a generic retrospective routing override.

#### Scenario: Recovery evidence does not match

- **WHEN** recovery is requested without an exact matching machine-local friction event and durable route identity
- **THEN** recovery is refused

#### Scenario: Recovery is used as a generic override

- **WHEN** recovery is requested for something other than a pure integration-head movement failure
- **THEN** it does not act as a generic retrospective routing override

### Requirement: Historic recovery uses a dedicated remote-provenance verifier

Recovery's remote-provenance proof SHALL use a verifier dedicated to the historical case, distinct from the live containment postcheck's verifier, and SHALL NOT require `after_head` to equal the checkout's *current* remote-tracking ref.

#### Scenario: Remote-tracking ref moved since execution

- **WHEN** the checkout's current remote-tracking ref no longer equals `after_head`
- **THEN** recovery's dedicated historical verifier does not require that equality

### Requirement: Historic recovery binds after_head to accepted history and the execution window

Recovery's remote-provenance proof SHALL require, all independently: `after_head` is an ancestor of (or equal to) the checkout's current remote-tracking main (proving it is real, accepted history and not an orphan/reset commit); and a durable local record (for example the remote-tracking ref's own reflog) shows `after_head` was that ref's value at a timestamp within the exact execution window already recorded on the flagged route's own evidence.

#### Scenario: Reflog shows after_head inside the window

- **WHEN** `after_head` is an ancestor of or equal to the current remote-tracking main and the remote-tracking reflog shows it as that ref's value within the recorded execution window
- **THEN** the remote-provenance proof is satisfied

### Requirement: Plain ancestry is not sufficient historical provenance

Plain ancestry to current main, without that durable temporal binding, SHALL NOT be treated as sufficient historical provenance.

#### Scenario: Only ancestry is proven

- **WHEN** `after_head` is an ancestor of current main but no durable temporal binding exists
- **THEN** it is not treated as sufficient historical provenance

### Requirement: The recovery binding window comes from the recovered route

The binding window SHALL be derived only from the durable route being recovered, never from a hardcoded external fact.

#### Scenario: Binding window is derived

- **WHEN** the recovery binding window is derived
- **THEN** it comes only from the durable route being recovered
- **AND** no hardcoded external fact is used

### Requirement: Successful recovery is mirrored into the durable routing record

A successful recovery SHALL mirror the completed execution and its nested recovery record into the durable integration-root routing record, using the same mechanism other completed executions use to do so, before reporting success.

#### Scenario: Recovery succeeds

- **WHEN** a recovery succeeds
- **THEN** the completed execution and its nested recovery record are mirrored into the durable integration-root routing record before success is reported

### Requirement: Recovery refuses closed when the durable record cannot be persisted

A failure to persist that durable record SHALL cause recovery to refuse closed without updating the task-local copy either, so a terminal routing/archive gate reading the durable record can never disagree with a reported successful recovery.

#### Scenario: Durable record write fails

- **WHEN** persisting the durable record fails during recovery
- **THEN** recovery refuses closed
- **AND** the task-local copy is not updated

### Requirement: The terminal gate accepts claimed Claude outcomes only on verifiable evidence

The terminal routing gate SHALL accept a claimed routine/standard Claude outcome only on the evidence the platform can verify (exact managed identity and a clean containment postcheck) and SHALL NOT present it as a confirmed launch.

#### Scenario: Claimed Claude outcome reaches the terminal gate

- **WHEN** a claimed routine/standard Claude outcome has exact managed identity and a clean containment postcheck
- **THEN** the terminal routing gate accepts it
- **AND** it is not presented as a confirmed launch

### Requirement: Reports do not count self-reported executions as launched

Efficiency and calibration reports SHALL NOT count a self-reported execution, current or legacy, as a launched or verified execution.

#### Scenario: Report includes a self-reported execution

- **WHEN** an efficiency or calibration report includes a current or legacy self-reported execution
- **THEN** it is not counted as a launched or verified execution

### Requirement: Directly observed execution paths keep their evidence semantics

Execution paths whose launch the platform observes directly, such as the platform-owned Codex subprocess, and the explicit retained outcome SHALL keep their existing evidence semantics.

#### Scenario: Platform-owned Codex subprocess

- **WHEN** the platform observes a launch directly, such as the platform-owned Codex subprocess
- **THEN** that execution keeps its existing evidence semantics

### Requirement: Cold-observation eligibility is not a universal size threshold

Eligibility SHALL remain configurable or evidence-driven in the initial capability; the platform SHALL NOT treat a research-specific size threshold as a universal invariant.

#### Scenario: Eligibility is decided

- **WHEN** eligibility of a large observation is decided in the initial capability
- **THEN** it is configurable or evidence-driven
- **AND** a research-specific size threshold is not treated as a universal invariant

### Requirement: Reducer evidence fields are validated against the source

Source handle/digest, exact quoted/ranged evidence and structured command/result fields SHALL be validated where applicable.

#### Scenario: Receipt carries evidence fields

- **WHEN** a reducer receipt carries a source handle/digest, quoted/ranged evidence or command/result fields
- **THEN** they are validated where applicable

### Requirement: Unverified reduction falls back to exact source evidence

Failure, low confidence or validation mismatch SHALL fall back to exact source evidence rather than produce a verified receipt.

#### Scenario: Reducer validation mismatch

- **WHEN** reduction fails, has low confidence or fails validation
- **THEN** exact source evidence is used
- **AND** no verified receipt is produced

### Requirement: Archive-time digest matches the source at reduction time

The archive-time digest SHALL also match the stored source at reduction time.

#### Scenario: Digest is checked

- **WHEN** a receipt's archive-time digest is checked
- **THEN** it matches the stored source at reduction time

### Requirement: A receipt is hot only when it is smaller

A receipt SHALL be used as the hot representation only when it is smaller than the source and the existing hot reference.

#### Scenario: Receipt is larger than the hot reference

- **WHEN** a receipt is not smaller than both the source and the existing hot reference
- **THEN** it is not used as the hot representation

### Requirement: Unreadable preserved source is reported as unavailable

If the preserved source cannot be read or fails integrity verification, reduction SHALL report source unavailability rather than claim that fallback evidence is recallable.

#### Scenario: Preserved source fails integrity

- **WHEN** the preserved source cannot be read or fails integrity verification
- **THEN** reduction reports source unavailability
- **AND** it does not claim that fallback evidence is recallable

### Requirement: Only stable models become production defaults

Only stable, production-eligible models SHALL become a production default; a prerelease, beta or RC model SHALL NOT.

#### Scenario: Prerelease model is proposed as default

- **WHEN** a prerelease, beta or RC model is proposed as a production default
- **THEN** it is not made the production default

### Requirement: Model binding changes ship through the release path

A binding change SHALL reach managed projects only through the existing immutable release and template update path, and SHALL be reversible by restoring the previous binding through that same path.

#### Scenario: Binding is changed and reverted

- **WHEN** a concrete model binding changes
- **THEN** it reaches managed projects only through the existing immutable release and template update path
- **AND** it is reversible by restoring the previous binding through that same path

### Requirement: Historical records keep their superseded model

Historical routing records naming a superseded model SHALL remain readable and be calibrated under their recorded model.

#### Scenario: Record names a superseded model

- **WHEN** a historical routing record names a superseded model
- **THEN** it remains readable and is calibrated under its recorded model

### Requirement: The execution plan is derived from policy and recorded separately

The plan SHALL be derived from routing policy and the explicit delegation request, and SHALL be recorded separately from the authored recommended tier and from the actual execution outcome.

#### Scenario: Plan is recorded

- **WHEN** route preparation records the execution plan
- **THEN** the plan is derived from routing policy and the explicit delegation request
- **AND** it is stored separately from the authored recommended tier and the actual execution outcome

### Requirement: Execution plan policies follow route profile and topology

A routine/standard route on a linked worktree SHALL be supervisor-retained with policy `balanced-parent` unless delegation is explicitly requested; a complex route SHALL be supervisor-retained with policy `complex-parent` and a route on a parent-only topology with policy `parent-only-topology`, regardless of a delegation request.

#### Scenario: Standard route on a linked worktree

- **WHEN** a routine/standard route on a linked worktree has no explicit delegation request
- **THEN** the plan is supervisor-retained with policy `balanced-parent`

#### Scenario: Complex route

- **WHEN** a complex route is prepared, with or without a delegation request
- **THEN** the plan is supervisor-retained with policy `complex-parent`

#### Scenario: Parent-only topology

- **WHEN** a route is prepared on a parent-only topology
- **THEN** the plan is supervisor-retained with policy `parent-only-topology` regardless of a delegation request

### Requirement: Route preparation fails on diverged task content

Route preparation SHALL fail explicitly when task content has already diverged from the materialized managed package. Divergence SHALL cover the full task tree: deleting, moving or renaming a tracked implementation path into an excluded lifecycle location (.claude/ or openspec/changes/) SHALL count as a change of the source path.

#### Scenario: Tracked path moved into a lifecycle location

- **WHEN** a tracked implementation path was moved into `openspec/changes/` before route preparation
- **THEN** the source path counts as changed
- **AND** route preparation fails explicitly

### Requirement: Claude delegation is opened by an explicit pre-launch step

For Claude, an explicit pre-launch step SHALL open the delegation, remain self-reported and SHALL NOT record a verified launch. Recording a Claude execution SHALL require that open delegation and SHALL be refused when no delegation was opened.

#### Scenario: Claude execution without an open delegation

- **WHEN** a Claude execution is recorded and no delegation was opened
- **THEN** recording is refused

#### Scenario: Claude pre-launch step

- **WHEN** the explicit Claude pre-launch step opens the delegation
- **THEN** the delegation remains self-reported
- **AND** no verified launch is recorded

### Requirement: Codex delegation opens only after the child process starts

Codex dispatch SHALL open a platform-observed delegation only once the child process has actually started.

#### Scenario: Codex child starts

- **WHEN** Codex dispatch runs
- **THEN** a platform-observed delegation is opened only once the child process has actually started

### Requirement: Pre-launch refusals record a closed not-launched attempt

Any refusal or failure before launch, including containment preflight, runtime/login preflight and spawn errors, SHALL immediately record a closed attempt with outcome not-launched. Such attempts SHALL never authorize supervisor-written content, retained finalization or escalation.

#### Scenario: Containment preflight refuses

- **WHEN** containment preflight, runtime/login preflight or spawn fails before launch
- **THEN** a closed attempt with outcome not-launched is recorded immediately
- **AND** it never authorizes supervisor-written content, retained finalization or escalation

### Requirement: The early routing gate runs before checks execute

The shared read-only early gate SHALL run in lifecycle status and finish, the check/test execution entrypoint and routing verification before any check executes, in addition to the archive gate.

#### Scenario: Check entrypoint is invoked

- **WHEN** the check/test execution entrypoint runs
- **THEN** the shared read-only early gate runs before any check executes

### Requirement: Routing records without a plan require re-routing

Records lacking a plan with no final execution outcome SHALL fail with an explicit re-route diagnostic rather than being accepted silently.

#### Scenario: Record lacks a plan

- **WHEN** a routing record lacks a plan and has no final execution outcome
- **THEN** the gate fails with an explicit re-route diagnostic

### Requirement: A pre-write hook denies unrouted implementation writes

The platform SHALL also apply the same rules as the shared read-only early gate at the first implementation write: a platform-installed Claude Code pre-write hook SHALL deny a file write targeting an active managed task worktree outside lifecycle paths when no route is recorded yet, when the active record has no plan and no final execution outcome, or when the plan is a delegated child without an open or completed delegation. The denial SHALL name the required next command.

#### Scenario: Write without a recorded route

- **WHEN** a file write targets an active managed task worktree outside lifecycle paths and no route is recorded yet
- **THEN** the platform-installed Claude Code pre-write hook denies it
- **AND** the denial names the required next command

### Requirement: The pre-write hook allows retained or delegated writes

A supervisor-retained plan or a real delegation SHALL allow the write with no additional step, and writes outside an active managed task SHALL NOT be affected.

#### Scenario: Supervisor-retained plan

- **WHEN** the plan is supervisor-retained or a real delegation exists
- **THEN** the write is allowed with no additional step

#### Scenario: Write outside a managed task

- **WHEN** a write is outside an active managed task
- **THEN** it is not affected

### Requirement: The pre-write hook is installed idempotently

The platform SHALL install this hook idempotently into the integration checkout's machine-local agent settings for multi-agent platform projects and SHALL fail explicitly when those settings are malformed.

#### Scenario: Malformed agent settings

- **WHEN** the integration checkout's machine-local agent settings are malformed during hook installation
- **THEN** installation fails explicitly

#### Scenario: Hook installed twice

- **WHEN** the hook is installed again into a multi-agent platform project
- **THEN** the settings are unchanged

### Requirement: Delegated-child plans are not converted to retained execution after changes

Apart from an explicit owner-approved retention, the platform SHALL NOT convert a delegated-child plan into retained execution after task content changed, SHALL NOT accept a Claude execution without an open delegation, and SHALL NOT permit an escalation to a supervisor-retained plan without a real recorded delegation or unchanged task content.

#### Scenario: Conversion after content changed

- **WHEN** task content changed under a delegated-child plan without an explicit owner-approved retention
- **THEN** the plan is not converted into retained execution

#### Scenario: Escalation to retained without delegation

- **WHEN** an escalation to a supervisor-retained plan is requested with changed task content and no real recorded delegation
- **THEN** it is not permitted

### Requirement: Recovery never writes events that did not occur

No recovery path SHALL write a launch claim, retrospective delegation or escalation trigger that did not occur.

#### Scenario: Recovery path runs

- **WHEN** any recovery path runs
- **THEN** it writes no launch claim, retrospective delegation or escalation trigger that did not occur

### Requirement: Owner-approved retention records the approval

The explicit owner-approved retention routing command SHALL require a non-empty owner approval statement and reason and SHALL record them with the approval time and the diverged paths in the plan.

#### Scenario: Retention is approved

- **WHEN** the owner-approved retention command runs with a non-empty approval statement and reason
- **THEN** the approval, reason, approval time and diverged paths are recorded in the plan

### Requirement: Owner-approved retention records no delegation

The explicit owner-approved retention routing command SHALL NOT record a delegation, launch claim or escalation and SHALL leave the routed profile unchanged.

#### Scenario: Retention switches the plan

- **WHEN** the owner-approved retention command switches the plan
- **THEN** no delegation, launch claim or escalation is recorded
- **AND** the routed profile is unchanged

### Requirement: Owner-approved retention is refused outside its preconditions

The explicit owner-approved retention routing command SHALL be refused, leaving the routing record unchanged, when the plan is already supervisor-retained, a real delegation was recorded, an execution other than a closed never-launched child attempt exists, task content is unchanged, or the approval or reason is empty.

#### Scenario: Plan already supervisor-retained

- **WHEN** the owner-approved retention command runs on a plan that is already supervisor-retained or with an empty approval
- **THEN** it is refused
- **AND** the routing record is unchanged

### Requirement: Owner-approved retention keeps a never-launched attempt

A never-launched attempt SHALL be kept as prior execution of the retained outcome.

#### Scenario: Prior never-launched attempt

- **WHEN** retention is approved after a closed child attempt that never launched
- **THEN** the attempt is kept as prior execution of the retained outcome

### Requirement: Owner-approved retained executions pass routing gates

A retained execution recorded under this policy SHALL carry the approval, the early and archive routing gates SHALL accept it, and routing reports SHALL mark the record owner-approved.

#### Scenario: Retained execution under owner approval

- **WHEN** a retained execution is recorded under the owner-approved policy
- **THEN** it carries the approval
- **AND** the early and archive routing gates accept it and routing reports mark it owner-approved

### Requirement: Owner-approved policy claims need a complete approval

A plan claiming the owner-approved policy without a complete recorded approval SHALL be invalid.

#### Scenario: Approval missing

- **WHEN** a plan claims the owner-approved policy without a complete recorded approval
- **THEN** the plan is invalid

### Requirement: Detection-only integration movement is classified by the receipt chain

For a detection-only delegated writer the platform SHALL classify integration-head movement as a verified concurrent advance only when no integration path was created, changed or disappeared, the new head is a fast-forward descendant equal to the recorded remote-tracking main, and an unbroken receipt chain from the pre-run head to the new head exists whose every acting worktree is outside the delegated worktree.

#### Scenario: Unbroken receipt chain

- **WHEN** a detection-only delegated writer observes a fast-forward integration move equal to the recorded remote-tracking main with no integration path change and an unbroken receipt chain from outside the delegated worktree
- **THEN** the movement is classified as a verified concurrent advance

### Requirement: Raw integration observation is kept beside its classification

The raw observation SHALL be preserved beside the classification.

#### Scenario: Movement is classified

- **WHEN** integration-head movement is classified
- **THEN** the raw observation is preserved beside the classification

### Requirement: Missing advance evidence remains a containment violation unless recovered with owner acceptance

Missing, broken, malformed or self-attributed evidence SHALL remain a containment violation. A historical violation recorded before receipts existed MAY be recovered only through an evidence-bound recovery tied to the exact friction event, the route's open delegation timing and the remote-tracking reflog, and only with an explicit recorded owner risk acceptance, because without receipts the platform cannot prove who moved integration main.

#### Scenario: Self-attributed receipt

- **WHEN** the advance evidence is missing, broken, malformed or self-attributed
- **THEN** the movement remains a containment violation

#### Scenario: Historical violation before receipts

- **WHEN** a violation recorded before receipts existed is recovered
- **THEN** the recovery is tied to the exact friction event, the route's open delegation timing and the remote-tracking reflog
- **AND** an explicit recorded owner risk acceptance is required

### Requirement: Pre-receipt recoveries are classified as owner-authorized

A recovery of a historical violation recorded before receipts existed SHALL be classified as an owner-authorized historical recovery, kept apart from any verified concurrent advance, and SHALL NOT be recorded as verified.

#### Scenario: Pre-receipt recovery is recorded

- **WHEN** a pre-receipt historical violation is recovered
- **THEN** it is classified as an owner-authorized historical recovery
- **AND** it is not recorded as verified

### Requirement: Receipted integration advances need no owner input

Integration advances that carry receipts SHALL be classified without any owner input.

#### Scenario: Advance with receipts

- **WHEN** an integration advance carries receipts
- **THEN** it is classified without any owner input

### Requirement: Sandboxed Claude dispatch launches and records a platform-observed writer

The platform SHALL itself launch a headless Claude writer through the sandboxed writer launch, SHALL open the delegation with `launch_evidence: platform-observed` only after the process started, and SHALL record the execution with mechanism `sandbox-runtime`, an executed participant and platform timing.

#### Scenario: Sandboxed dispatch starts

- **WHEN** sandboxed Claude dispatch runs for a prepared `delegated-child` Claude route
- **THEN** the platform launches the headless writer and opens the delegation with `launch_evidence: platform-observed` only after the process started
- **AND** the execution is recorded with mechanism `sandbox-runtime`, an executed participant and platform timing

### Requirement: The terminal gate accepts platform-observed sandboxed Claude execution

The terminal routing gate SHALL accept a completed platform-observed sandboxed Claude execution without the detection-only integration postcheck.

#### Scenario: Completed sandboxed execution

- **WHEN** a completed platform-observed sandboxed Claude execution reaches the terminal routing gate
- **THEN** it is accepted without the detection-only integration postcheck

### Requirement: Native Agent-tool hand-off stays the default Claude path

The native Agent-tool hand-off SHALL remain the default Claude path with its existing self-reported semantics.

#### Scenario: Claude route without sandboxed dispatch

- **WHEN** a Claude route does not use sandboxed dispatch
- **THEN** the native Agent-tool hand-off is used with its existing self-reported semantics

### Requirement: Sandboxed Claude pre-launch refusal records a not-launched attempt

A pre-launch refusal of the sandboxed Claude dispatch SHALL record a closed not-launched attempt.

#### Scenario: Sandboxed dispatch refused before launch

- **WHEN** sandboxed Claude dispatch is refused before launch
- **THEN** a closed not-launched attempt is recorded

### Requirement: Standalone-clone postcheck accepts only descendant HEAD moves

For a supervisor-retained route in the `standalone-clone` topology with no delegated child, the containment postcheck SHALL accept a HEAD move only when the current HEAD is a descendant of the snapshot HEAD, and SHALL still report a violation for a non-descendant HEAD, for any new, changed or vanished path in the working tree other than platform lifecycle records, and for any change to a path that was already dirty at the snapshot.

#### Scenario: Non-descendant HEAD

- **WHEN** the containment postcheck runs for a supervisor-retained `standalone-clone` route and HEAD is not a descendant of the snapshot HEAD
- **THEN** it reports a violation

#### Scenario: Previously dirty path changed

- **WHEN** a path that was already dirty at the snapshot changed
- **THEN** the postcheck reports a violation

### Requirement: Linked-worktree routes keep the existing postcheck

Routes in the linked-worktree topology SHALL keep the existing postcheck.

#### Scenario: Linked-worktree route

- **WHEN** the containment postcheck runs for a route in the linked-worktree topology
- **THEN** the existing postcheck applies

### Requirement: Shipped hints name only commands that exist in a rendered project

Shipped hints, errors and docs SHALL name only commands that exist in a rendered project.

#### Scenario: Hint names a command

- **WHEN** a shipped hint, error or doc names a command
- **THEN** that command exists in a rendered project

### Requirement: The managed task state file is not committed to a project

The managed task state file SHALL NOT be committed to a project's repository.

#### Scenario: Project commit

- **WHEN** a project's repository is committed
- **THEN** the managed task state file is not part of the commit

### Requirement: Source route commands take a routing tier

`dogfood_task.py route-claude` and `route-codex` SHALL take `--tier R1|R2|R3` and route as the profile it maps to (R1 routine, R2 standard, R3 complex); omitting it SHALL confirm the authored tier. `--profile` SHALL be refused with an error naming `--tier`. Source docs and hints SHALL name only R1/R2/R3 for these commands.

#### Scenario: Explicit tier
- **WHEN** `route-claude --tier R2` runs
- **THEN** it records the same route as the former `--profile standard`

#### Scenario: Old flag
- **WHEN** `route-codex --profile standard` runs
- **THEN** it fails naming `--tier` and records nothing
