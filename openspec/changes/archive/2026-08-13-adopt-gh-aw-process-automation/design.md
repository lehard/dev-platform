## Context

The change started when `dev-platform` had three gaps at once: no cloud review runtime, a manual friction-promotion path, and no structural completion trigger that forced an agent to decide whether meaningful friction had occurred. The first gap is solved and proven in production-like acceptance: pinned `gh-aw` workflows run Codex inside GitHub Actions with bounded cost/runtime, read-only analysis and constrained `safe-outputs`. The local routing/checkpoint path is also largely implemented.

Three other platform capabilities materially shape the remaining design:

- `durable-publication-recovery` provides the stable platform-owned `finish_task`/publication boundary and resumable GitHub-backed lifecycle.
- managed-task authoring provides a separate intentional path from an accepted human decision to `lehard/development-backlog` plus OpenSpec. Process/friction issues therefore remain evidence, not a second managed-task queue.
- provider-local `model-routing` now records semantic execution profile, selected executor model and delegation evidence for managed tasks. Codex lower-cost execution is launched through the platform path; Claude lower-cost execution is handed to a native Agent call and later records the returned agent id.

Real operation exposed two remaining quality gaps. A friction checkpoint can be mechanically closed without a separate retrospective, and friction evidence has no bounded execution provenance. The latter makes it impossible to reliably distinguish a behaviour of Codex from Claude Code, a parent from a delegated child, or a configured route from the route that actually ran.

The design should optimize for truthful evidence and few moving parts, not for a generalized tracing or self-improving-agent framework.

## Goals

- Make significant process friction hard to forget at the ordinary platform-owned completion boundary through a bounded post-task retrospective.
- Preserve `0..N` unresolved findings from one retrospective without requiring a human follow-up prompt.
- Attach enough truthful execution provenance to task/friction evidence to distinguish runtime/provider, supervisor vs delegated executor, execution profile and model where those values are provable.
- Preserve the difference between selected/configured execution metadata and runtime-confirmed metadata; never fabricate unknown model/effort values.
- Attribute a finding to a delegated child only when the platform has evidence that the child actually ran.
- Route useful sanitized evidence to the correct GitHub issue backlog without a remembered `promote` command.
- Prevent duplicate issue spam with deterministic, non-secret identity.
- Preserve raw evidence locally and survive temporary GitHub/auth/network failure without blocking safe publication.
- Reuse the working model-routing, friction and `gh-aw` layers rather than add another scheduler, memory system, transcript store or review daemon.
- Keep an explicit human decision between process evidence and a managed implementation task.

## Non-goals

- A general-purpose distributed tracing/observability backend for agents.
- Transcript, prompt, chain-of-thought or full tool-call warehousing.
- Autonomous code fixes, OpenSpec creation/acceptance, Development Backlog creation or executor dispatch from process issues.
- Model-specific behavioural corrections in the same change; provenance is the evidence base for later corrections.
- A local cron/launchd daemon, new background service or MemoryOps state.
- Per-agent Claude/Codex hooks as the primary completion enforcement mechanism.
- Claiming effective reasoning effort from a configuration value when the runtime cannot confirm that it was actually applied.
- Cross-provider delegation or a unified vendor telemetry API.
- Full Repo Assist or Process Analyzer adoption in this change.
- Downstream rollout of `gh-aw` cloud workflows to managed consumer repositories.

## Decisions

### 1. Preserve the working cloud pilot

`Process Issue Triage` and `Weekly Process Backlog Review` remain the cloud advisory layer. Their existing engine, safe-output boundary, public-only MCP constraints, gateway compatibility pinning, timeout and AI-credit limits are retained unless a concrete acceptance or maintenance failure requires adjustment.

Cloud workflow success is not part of deterministic CI/publication/release correctness.

### 2. One normal local path: record, then route

The normal friction flow remains:

`structured local event -> sanitized candidate -> deterministic GitHub issue upsert -> gh-aw triage/review`

The existing local JSONL remains useful as raw evidence and retry storage. The separate batch-review cursor is not part of normal operator completion work.

`pending`, `review`, `mark-reviewed` and `promote` MAY remain temporarily for recovery/backward compatibility, but generated guidance SHALL not present them as routine completion work.

### 3. Process issues and managed tasks are different state machines

A friction/process issue represents evidence: something went wrong, repeated, required a workaround, exposed an invariant, or may justify process improvement.

A Development Backlog issue represents an explicit human decision to manage and later implement a change. `gh-aw` triage/review SHALL NOT cross this boundary automatically.

If review says a process issue is ready for remediation, the output is advisory. Only explicit human fixation intent invokes managed-task authoring.

### 4. Completion enforcement lives at the platform lifecycle boundary

For a non-trivial platform-owned task, terminal completion requires a bounded post-task retrospective tied to the current task execution state. The retrospective examines material work history available to the agent and produces `0..N` unresolved/unrecorded high-signal findings after excluding problems already fixed in the task and existing recorded duplicates.

A clean retrospective resolves to `none`; a positive retrospective resolves to all newly recorded event references. A bare `checkpoint --result none` without evidence that the retrospective ran is insufficient.

The exact minimal receipt shape is implementation-owned and should reuse `finish_task` rather than introduce a parallel state machine. Per-agent hooks may remain compatible helpers, but correctness belongs to the shared repository lifecycle so Codex and Claude follow the same contract.

### 5. Deterministic failures record themselves

When a lifecycle component can mechanically classify a high-signal failure or safety near-miss, it should create the structured local friction event directly with bounded context. Model judgment is reserved for semantic friction such as user correction, false premise or repeated workaround.

Do not instrument every exception. Only supported high-signal lifecycle/process categories belong in automatic capture.

### 6. Routing is deterministic and sanitized

The router resolves destination from event scope:

- `project` -> normalized current GitHub repository;
- `platform` -> configured platform promotion repository.

The public issue representation contains only bounded sanitized fields such as source repository/project, category/key, severity, occurrence metadata, concise observation/proposal and the minimum useful execution provenance. Raw arbitrary evidence and unnecessary machine-local details stay local by default.

The router uses existing authenticated GitHub access. It does not invoke an LLM to decide where or how to write the issue.

### 7. Stable fingerprint owns deduplication

Each routable event has a stable non-secret fingerprint derived only from normalized machine-safe identity fields such as destination scope/repository plus category/key. Execution model/version MUST NOT be added to the canonical friction fingerprint merely to split the same underlying process problem by model; model/runtime is occurrence provenance for later comparison.

The canonical issue stores a machine-readable marker containing that fingerprint. Repeated occurrences update the same open issue with bounded occurrence metadata rather than create one issue per model/run.

### 8. Routing failure is durable and non-blocking

A recorded event has explicit local routing state sufficient to distinguish pending from successfully routed. If GitHub auth/network/API access is unavailable, the event remains pending and a concise non-secret warning is emitted.

A later supported lifecycle invocation retries pending routing. Telemetry failure alone does not turn an otherwise safely delivered task into failed publication. No retry daemon is introduced.

### 9. Weekly review remains advisory and bounded

The scheduled weekly workflow summarizes process issues, likely duplicates, stale/already-resolved candidates, missing evidence and items ready for a human decision. Once provenance exists it MAY compare repeated occurrences by runtime/model, but it cannot infer causality from one observation or auto-create model-specific fixes.

The acceptance requirement remains at least one genuine scheduled run; a manual `workflow_dispatch` does not substitute for that evidence.

### 10. Keep the central pilot boundary

This change completes the central `dev-platform` loop only. Consumer cloud-workflow rollout is a separate future managed change after the central behavior proves useful over real work.

### 11. Execution provenance is bounded metadata, not a trace warehouse

The platform needs a small execution record sufficient for attribution, not a transcript. A run/participant record should carry only fields that are useful and supportable, such as:

- runtime/provider (`codex`, `claude` or another explicitly supported value);
- participant role (`supervisor` or delegated `executor`);
- execution profile (`routine`, `standard`, `complex`) when routing owns one;
- model identity when selected or confirmed;
- reasoning effort when selected or confirmed;
- provenance source/status for model and effort, distinguishing at least platform-selected/configured, runtime-confirmed and unknown;
- actual delegation evidence such as execution status and a bounded runtime agent/thread identifier when the supported runtime returns one;
- parent/child relationship when a delegated participant actually ran.

The platform SHOULD reuse the current model-routing record and friction/lifecycle state instead of creating a second persistent run database. The exact normalized field names are implementation-owned.

### 12. Machine-owned evidence wins over model self-identification

Free-form statements such as “I am model X” are not authoritative provenance. The evidence hierarchy is:

1. structured metadata returned by the supported runtime for the actual session/turn/agent, when available;
2. platform-owned routing/launch metadata for a value the platform explicitly selected and passed to the runtime;
3. explicit `unknown` when neither source can truthfully establish the value.

Selected/configured and runtime-confirmed are different states. In particular, a configured reasoning effort is not evidence that the runtime actually honored it. If the runtime only proves the selected effort, store it as selected/configured; if it exposes the effective value for the actual execution, it may additionally be marked runtime-confirmed.

A missing field does not block otherwise valid work merely to force the model to invent it.

### 13. Provider adapters stay thin and are verified against the current runtime

The shared contract is provider-neutral, while data acquisition may differ at the runtime edge.

For routed Codex children, the current platform already owns the selected executor model and launch outcome. Implementation preflight must verify the current supported Codex surface for selected/effective reasoning effort and parent-session metadata before adding those fields. If a stable surface is unavailable, the corresponding value remains unknown rather than being inferred from global config or a model response.

For routed Claude children, the current hand-off already selects a child model/effort and `record_claude_execution` records a real returned agent id after the Agent call. Those facts can seed child provenance, while implementation preflight still verifies whether the current runtime exposes stronger runtime-confirmed session/model metadata.

For strong interactive supervisors in either runtime, use structured runtime metadata only where a supported current surface exists. The platform does not add fragile UI scraping or transcript parsing solely to fill optional provenance fields.

### 14. Friction points to the participant that observed/caused it when knowable

A friction event or retrospective finding should reference the current execution/run and, when evidence permits, the relevant participant. This lets later analysis distinguish “Claude supervisor asked for an unnecessary confirmation” from “delegated Sonnet executor hit a verification blocker” without attributing both to the task as a whole.

If the locus is ambiguous, the finding attaches to the run with participant unknown rather than inventing blame. Orchestrator/handoff problems may correctly belong to the supervisor even when symptoms appear during child work.

Prepared-but-not-executed routes are never represented as executed child participants. Fallback and escalation must preserve the actual route that ran.

## Updated execution shape

1. Preserve current cloud pilot and its validation.
2. Keep local friction routing/deduplication and completion checkpoint semantics.
3. Add the bounded post-task retrospective tied to current task execution state.
4. Extend the existing route/completion evidence with truthful bounded participants and provenance source/status.
5. Attach retrospective/friction findings to that run/participant evidence and expose only bounded sanitized provenance publicly.
6. Prove the contract on a real supported Claude Code run, including delegation and an unknown/unavailable metadata case (done: real `route-claude` -> Agent-tool -> `record-claude-execution` delegation). The equivalent real Codex run is deliberately split into a small dedicated follow-up (`lehard/development-backlog#33`) rather than holding this change open for an external account rate-limit reset; the Codex path itself is implemented and unit-tested here against realistic captured `--json` event lines.
7. Observe the required real scheduled weekly review.
8. Perform semantic verification, archive and release only when all acceptance evidence is truthful.

## Risks and mitigations

- **Checkpoint becomes ceremony:** require a bounded retrospective result rather than a bare remembered `none` call.
- **False model attribution:** machine-owned evidence hierarchy; explicit `unknown`; prepared routes do not count as executions.
- **Configured effort mistaken for effective effort:** persist provenance source/status and never upgrade configured to runtime-confirmed without evidence.
- **Provider/runtime drift:** verify actual supported Codex/Claude surfaces at implementation preflight; keep provider adapters thin and fail truthfully.
- **Overengineering:** reuse model-routing/friction/lifecycle state; no tracing backend, transcript store, daemon or general telemetry service.
- **Issue spam:** deterministic fingerprint remains process-problem based rather than model based; model/runtime is occurrence metadata.
- **Sensitive leakage:** raw evidence local by default; strict sanitization and bounded public provenance.
- **GitHub outage:** local pending state and later lifecycle retry; no daemon.
- **AI self-modification:** process review cannot create Development Backlog tasks or implementation PRs.
- **Preview churn in `gh-aw`:** retain exact tested pins and existing deterministic source/lock validation.
