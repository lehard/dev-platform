## Why

Source backlog issue: `lehard/development-backlog#5`  
Prepared against: `lehard/dev-platform@6d2629db8b5f4e6ed6dbdcdaa5dba8a0ddd14d8a`

The `gh-aw` cloud pilot and automatic process-friction routing are already proven, and the platform-owned completion lifecycle now has an explicit friction checkpoint. Real use has exposed two remaining gaps.

First, a model can still satisfy the checkpoint mechanically without performing a separate bounded retrospective over the work that just happened. A clean completion therefore needs an explicit post-task review that can produce `0..N` unresolved findings rather than relying on model memory or a human reminder.

Second, friction evidence currently does not say which execution participant actually did the work. That matters now that the platform supports provider-local routing: Codex and Claude Code have different observable behaviours, and a strong supervisor may delegate implementation to a cheaper subagent. Without bounded execution provenance, later review can incorrectly attribute a blocker, retry pattern or unnecessary human interaction to the parent, the child, or even the wrong runtime.

This provenance must be truthful rather than conversational self-identification. The current model-routing path already records provider, execution profile, selected executor model and actual delegation evidence; the Claude hand-off also carries the selected child model/effort and records the returned agent id. Those machine-owned records are the preferred source. Interactive parent metadata and effective reasoning effort are recorded only when the current runtime exposes them reliably; otherwise the field remains explicitly unknown. A configured/selected value must not be silently relabelled as runtime-confirmed execution state.

The platform has a separate managed-task authoring path through the Development Backlog, so the source-of-truth boundary stays unchanged: process/friction issues are evidence about how development went wrong; a Development Backlog issue plus OpenSpec is an explicitly accepted future change. Neither retrospective nor provenance may silently convert evidence into managed work.

The remaining implementation should therefore stay small: complete the bounded retrospective, attach truthful bounded execution provenance to task/friction evidence using existing lifecycle and routing state, and preserve the working `capture -> sanitized GitHub issue upsert -> gh-aw triage/review` loop. No tracing backend, transcript warehouse, second scheduler, agent memory system, background daemon or autonomous remediation loop is needed.

## What Changes

- Keep the accepted `gh-aw + Codex` process-triage and weekly-review pilot as the cloud advisory layer; do not redesign it without a demonstrated compatibility/security need.
- Keep the normal local friction path `capture -> sanitized GitHub issue upsert -> gh-aw triage/review` and the existing routing/dedupe/sanitization/offline-retry guarantees.
- Require a bounded post-task process retrospective before terminal completion of a non-trivial platform-owned task. It may produce `0..N` unresolved findings; `none` is valid only after that retrospective ran.
- Bind the retrospective/checkpoint to the current task execution state so a stale receipt cannot close changed work.
- Add bounded execution provenance sufficient to distinguish the runtime/provider, supervisor vs delegated executor, execution profile, selected/confirmed model, reasoning effort when truthfully knowable, and the parent-child identity of a real delegated run.
- Prefer machine-owned runtime/routing evidence over free-form model self-identification. Distinguish selected/configured metadata from runtime-confirmed metadata, and record `unknown` when a value cannot be proven by the supported current runtime.
- Reuse existing model-routing and friction/lifecycle records rather than build a parallel tracing or observability subsystem.
- Link model-observed friction and retrospective findings to the relevant execution participant/run when that attribution is known. Do not claim a subagent executed work merely because a route was prepared.
- Record supported deterministic lifecycle/process failures directly where they are mechanically observable instead of relying on model memory.
- Route only bounded sanitized provenance with public friction evidence; raw evidence and any machine-local execution detail that is not needed publicly stay local by default.
- Explicitly separate process evidence from managed work: `gh-aw` may triage, summarize, compare recurring model/runtime patterns and recommend remediation, but SHALL NOT create Development Backlog tasks, materialize OpenSpec changes, modify code or dispatch executors. A managed task appears only after explicit human fixation intent.
- Keep the cloud-workflow pilot central to `dev-platform` in this change. Do not roll `gh-aw` workflows into Cuby, Jara_Fin or Planner Agent Lab here.

## Capabilities

### New Capabilities

- `agentic-maintenance`: Safe, bounded cloud triage and periodic review of process evidence using GitHub Agentic Workflows and Codex.

### Modified Capabilities

- `platform-lifecycle`: Make a real post-task retrospective, meaningful friction capture, truthful execution provenance and sanitized routing normal completion evidence instead of a remembered manual ritual.
- `model-routing`: Preserve bounded truthful evidence of the route that actually executed so downstream friction can be attributed to the supervisor/executor without inventing model or effort metadata.

## Impact

The remaining implementation is expected to touch the friction helper, model-routing execution record, the stable platform-owned completion lifecycle, generated cross-agent guidance, deterministic tests and OpenSpec evidence. Provider-specific code should remain a thin edge adapter around the shared contract and must be validated against the currently supported Codex and Claude Code runtime surfaces during implementation preflight.

The change does not own model-specific behavioural fixes, a generic analytics warehouse, Development Backlog authoring, managed-task execution/publication, or autonomous remediation. Those remain separate concerns; this change creates trustworthy evidence on which later model/runtime-specific corrections can be based.
