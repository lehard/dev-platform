## Why

Source backlog issue: `lehard/development-backlog#5`  
Originally prepared against: `lehard/dev-platform@c89a809123265e842187aa5b14959533f995416e`  
Refined against: `lehard/dev-platform@07ab9565909996bf710d56bd5903a5fe709139ff`

The `gh-aw` cloud pilot is already proven, sanitized friction routing/deduplication/retry is implemented, and the platform-owned completion lifecycle already requires an explicit friction checkpoint. Real use exposed a narrower remaining gap: the checkpoint can become ceremony. An agent may resolve it as `none` without first performing a separate analysis of the work that just happened, while a later human reminder to review process friction still regularly surfaces additional unresolved findings.

The contract therefore needs to distinguish **having a checkpoint value** from **having performed a post-task process retrospective**. For non-trivial platform-owned work, terminal completion should require a bounded retrospective pass that reviews the task for high-signal unresolved/unrecorded friction, records every meaningful new finding, and only then produces the completion result. `none` is valid only after that review finds no new meaningful unresolved/unrecorded friction.

This refinement stays inside the existing friction/completion architecture. Process issues remain evidence, not managed tasks; the working cloud pilot remains advisory; no new scheduler, memory subsystem, transcript warehouse, autonomous remediation loop, or parallel lifecycle state machine is introduced.

## What Changes

- Keep the accepted `gh-aw + Codex` process-triage and weekly-review pilot as the cloud advisory layer.
- Keep the normal local path `capture -> sanitized GitHub issue upsert -> gh-aw triage/review`, including existing sanitization, deterministic dedupe and durable retry behavior.
- Strengthen non-trivial platform-owned completion from a bare `none | event` checkpoint into a required bounded post-task process retrospective followed by a current-task completion receipt.
- Require the retrospective to inspect semantic friction signals including user corrections, repeated failures/retries, manual workarounds, safety near-misses, false premises, undocumented invariants, missing automation/documentation, tooling/auth/worktree/Git/OpenSpec/CI/lifecycle friction, avoidable repeated work, and problems noticed but left unresolved.
- Filter candidates before recording: findings already fixed in the task or already represented by existing friction/process evidence are not emitted again; new meaningful unresolved/unrecorded findings are recorded.
- Support `0..N` retrospective findings/events. `none` means the retrospective ran and produced zero new meaningful unresolved/unrecorded findings; it no longer means merely that the agent chose not to record anything.
- Make retrospective completion evidence fresh enough for the current task execution state that a stale checkpoint cannot silently satisfy changed/new work. The exact technical identity binding is implementation-owned after preflight, but should reuse existing task/branch/head lifecycle evidence rather than create a second state machine.
- Make the authoritative `finish_task` completion boundary reject missing or stale retrospective evidence before terminal completion.
- Keep machine-detectable lifecycle/process failures recorded directly where they are mechanically observable instead of waiting for the final retrospective.
- Update generated cross-agent guidance so Codex and Claude perform this review without a human natural-language reminder and report its result concisely at the end.
- Preserve the boundary between process evidence and managed work: neither retrospective nor `gh-aw` may create Development Backlog tasks, materialize OpenSpec, modify code, or dispatch executors automatically.
- Keep the pilot central to `dev-platform`; downstream `gh-aw` rollout remains separate.

## Capabilities

### New Capabilities

- `agentic-maintenance`: Safe, bounded cloud triage and periodic review of process evidence using GitHub Agentic Workflows and Codex.

### Modified Capabilities

- `platform-lifecycle`: Make post-task friction discovery, multi-finding capture, freshness-aware completion evidence, and sanitized routing part of the normal Definition of Done for non-trivial platform-owned work.

## Impact

The remaining implementation should stay focused on the friction helper/checkpoint representation, authoritative completion lifecycle, generated agent guidance, deterministic tests, and final OpenSpec evidence. The existing routing/cloud-workflow implementation should change only where required by the stronger retrospective contract.

The change does not own Development Backlog authoring, autonomous remediation, a general transcript-analysis product, or a second implementation planner. Repository-local `openspec/changes/adopt-gh-aw-process-automation/` remains the canonical implementation contract once this revision is materialized/reconciled.
