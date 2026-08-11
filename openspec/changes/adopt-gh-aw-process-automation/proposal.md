## Why

Source backlog issue: `lehard/development-backlog#5`  
Prepared against: `lehard/dev-platform@c89a809123265e842187aa5b14959533f995416e`

The `gh-aw` cloud pilot is already proven: Codex runs in GitHub Actions, controlled process issues can be read, mutations are constrained through `safe-outputs`, and representative cost/runtime evidence exists. The remaining gap is local process-friction capture. Today the normal agent guidance still depends on a remembered `pending/review/mark-reviewed/promote` ritual and on the model noticing that a problem should be recorded at all.

The platform has also gained a separate managed-task authoring path through the Development Backlog. That makes the source-of-truth boundary clearer than when this change was first drafted: a process/friction issue is evidence about how development went wrong; a Development Backlog issue plus OpenSpec is an explicitly accepted future change. Automation must not silently convert the former into the latter.

The remaining work should therefore be smaller than the original design: preserve the working cloud pilot, make friction capture unavoidable at the platform-owned completion boundary, route sanitized events directly to GitHub Issues with deterministic deduplication and retry, and let `gh-aw` triage/review that evidence. No second scheduler, agent memory system, background daemon or autonomous remediation loop is needed.

## What Changes

- Keep the already accepted `gh-aw + Codex` process-triage and weekly-review pilot as the cloud advisory layer; do not redesign it without a demonstrated compatibility/security need.
- Simplify the normal local friction path to `capture -> sanitized GitHub issue upsert -> gh-aw triage/review`.
- Make a minimal explicit friction checkpoint part of non-trivial platform-owned task completion so the agent must resolve either `friction: none` or identify a recorded structured event before reporting completion.
- Record supported deterministic lifecycle/process failures directly where they are mechanically observable instead of relying on model memory.
- Route sanitized high-signal friction automatically: `scope=project` to the current repository and `scope=platform` to the configured platform repository. Raw evidence stays machine-local by default.
- Deduplicate by a stable non-secret fingerprint/marker so repeated occurrences update one open issue with bounded occurrence metadata rather than creating issue spam.
- Keep routing failure non-blocking for otherwise safe publication: an unrouted event stays pending locally and is retried on a later supported lifecycle invocation.
- Remove `pending/review/mark-reviewed/promote` from the normal agent/operator path. Existing commands MAY remain temporarily as recovery/backward-compatible surfaces, but they are no longer the expected workflow.
- Explicitly separate process evidence from managed work: `gh-aw` may triage, summarize, identify stale/duplicate/resolved candidates and recommend remediation, but SHALL NOT create Development Backlog tasks, materialize OpenSpec changes, modify code or dispatch executors. A managed task appears only after explicit human fixation intent through the normal authoring contract.
- Keep the pilot central to `dev-platform` in this change. Do not roll `gh-aw` workflows into Cuby, Jara_Fin or Planner Agent Lab here.

## Capabilities

### New Capabilities

- `agentic-maintenance`: Safe, bounded cloud triage and periodic review of process evidence using GitHub Agentic Workflows and Codex.

### Modified Capabilities

- `platform-lifecycle`: Make meaningful friction capture plus sanitized routing a normal completion invariant instead of a remembered manual promotion ritual.

## Impact

The remaining implementation is expected to touch the friction helper, the stable platform-owned completion lifecycle, generated agent guidance, deterministic tests and OpenSpec evidence. The existing agentic workflow sources/locks should change only if current validation or acceptance exposes a concrete defect.

The change does not own Development Backlog authoring, managed-task execution/publication, or autonomous remediation. Those remain separate platform capabilities with a deliberate human boundary between process evidence and accepted managed work.
