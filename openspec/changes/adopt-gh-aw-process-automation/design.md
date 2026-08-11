## Context

The change started when `dev-platform` had three gaps at once: no cloud review runtime, a manual friction-promotion path, and no structural completion trigger that forced an agent to decide whether meaningful friction had occurred. The first gap is now solved and proven in production-like acceptance: pinned `gh-aw` workflows run Codex inside GitHub Actions with bounded cost/runtime, read-only analysis and constrained `safe-outputs`.

Two other platform changes have since landed and materially simplify the remaining design:

- `durable-publication-recovery` provides the stable platform-owned `finish_task`/publication boundary and resumable GitHub-backed lifecycle.
- managed-task authoring provides a separate intentional path from an accepted human decision to `lehard/development-backlog` plus OpenSpec. Process/friction issues therefore must remain evidence, not a second managed-task queue.

The remaining design should optimize for reliability and few moving parts, not for a generalized self-improving agent framework.

## Goals

- Make significant process friction hard to forget at the ordinary platform-owned completion boundary.
- Route useful sanitized evidence to the correct GitHub issue backlog without a remembered `promote` command.
- Prevent duplicate issue spam with deterministic, non-secret identity.
- Preserve raw evidence locally and survive temporary GitHub/auth/network failure without blocking safe publication.
- Reuse the working `gh-aw` triage/review layer rather than add another scheduler, memory system or review daemon.
- Keep an explicit human decision between process evidence and a managed implementation task.

## Non-goals

- Autonomous code fixes, OpenSpec creation/acceptance, Development Backlog creation or executor dispatch from process issues.
- A local cron/launchd daemon, new background service, MemoryOps state, or transcript export pipeline.
- Per-agent Claude/Codex hooks as the primary completion enforcement mechanism.
- Full Repo Assist or Process Analyzer adoption in this change.
- Downstream rollout of `gh-aw` workflows to managed consumer repositories.
- Removing every legacy friction CLI command in the same change when keeping it as a recovery surface is cheaper and safer.

## Decisions

### 1. Preserve the working cloud pilot

`Process Issue Triage` and `Weekly Process Backlog Review` remain the cloud advisory layer. Their existing engine, safe-output boundary, public-only MCP constraints, gateway compatibility pinning, timeout and AI-credit limits are retained unless a concrete acceptance or maintenance failure requires adjustment.

Cloud workflow success is not part of deterministic CI/publication/release correctness.

### 2. One normal local path: record, then route

The normal friction flow becomes:

`structured local event -> sanitized candidate -> deterministic GitHub issue upsert -> gh-aw triage/review`

The existing local JSONL remains useful as raw evidence and as a retry queue. The separate batch-review cursor is no longer part of the normal operator flow.

`pending`, `review`, `mark-reviewed` and `promote` MAY remain temporarily for recovery/backward compatibility, but generated guidance SHALL stop presenting them as routine completion work.

### 3. Process issues and managed tasks are different state machines

A friction/process issue represents evidence: something went wrong, repeated, required a workaround, exposed an invariant, or may justify process improvement.

A Development Backlog issue represents an explicit human decision to manage and later implement a change. `gh-aw` triage/review SHALL NOT cross this boundary automatically.

If weekly review says a process issue is ready for remediation, the output is advisory. Only explicit human fixation intent invokes the existing managed-task authoring path.

### 4. Completion enforcement lives at the platform lifecycle boundary

For a non-trivial platform-owned task, completion must resolve one small checkpoint:

- `friction: none`; or
- `friction: <structured event reference>`.

The exact minimal CLI/receipt shape is implementation-owned and should reuse the final `finish_task` lifecycle rather than introduce a parallel state machine. The checkpoint must be deterministic enough that a non-trivial task cannot silently omit it, while `none` must not create GitHub noise.

Per-agent hooks may remain compatible helpers, but they are not required for correctness because Codex and Claude must share the same repository lifecycle contract.

### 5. Deterministic failures record themselves

When a lifecycle component can mechanically classify a high-signal failure or safety near-miss, it should create the structured local friction event directly with bounded context. Model judgment is reserved for semantic friction such as user correction, false premise or repeated workaround.

Do not instrument every exception. Only supported high-signal lifecycle/process categories belong in automatic capture.

### 6. Routing is deterministic and sanitized

The router resolves destination from event scope:

- `project` -> normalized current GitHub repository;
- `platform` -> configured platform promotion repository.

The issue representation contains bounded sanitized fields such as source repository/project, category/key, severity, first/last occurrence and a concise observation/proposal summary. Raw arbitrary evidence stays local by default.

The router uses existing authenticated GitHub CLI/API access. It does not invoke an LLM to decide where or how to write the issue.

### 7. Stable fingerprint owns deduplication

Each routable event has a stable non-secret fingerprint derived only from normalized machine-safe identity fields such as destination scope/repository plus category/key. It must not contain raw evidence, credentials, arbitrary user text or secret-bearing absolute paths.

The canonical issue stores a machine-readable marker containing that fingerprint. Routing first looks for an open issue with the marker:

- if found, append/update a bounded sanitized occurrence;
- if not found, create one issue.

Closed historical issues are not silently reopened unless implementation evidence shows reopening is the desired contract; a new occurrence after closure may create a new current issue while preserving the old history.

### 8. Routing failure is durable and non-blocking

A recorded event has explicit local routing state sufficient to distinguish pending from successfully routed. If GitHub auth/network/API access is unavailable, the event remains pending and a concise non-secret warning is emitted.

A later supported lifecycle invocation (`doctor`, task start or finish; choose the narrowest implementation surface) retries pending routing. Telemetry failure alone does not turn an otherwise safely delivered task into failed publication.

No separate retry daemon is introduced.

### 9. Weekly review remains advisory and bounded

The scheduled weekly workflow summarizes process issues, likely duplicates, stale/already-resolved candidates, missing evidence and items ready for a human decision. It may use bounded safe outputs already declared by the pilot.

The acceptance requirement is at least one genuine scheduled run; a manual `workflow_dispatch` does not substitute for that evidence.

### 10. Keep the central pilot boundary

This change completes the central `dev-platform` loop only. Consumer workflow rollout is a separate future managed change after the central behavior proves useful over real work.

## Updated execution shape

1. Preserve current cloud pilot and its validation.
2. Simplify local friction storage/routing and retire the manual promotion ritual from normal guidance.
3. Integrate the minimal completion checkpoint into the now-stable platform-owned lifecycle.
4. Prove deterministic dedupe, sanitization and offline retry with controlled acceptance.
5. Observe one real scheduled weekly review.
6. Perform semantic verification, archive and release only when all acceptance evidence is truthful.

## Risks and mitigations

- **Checkpoint becomes ceremony:** keep it binary/minimal and create no issue when the result is `none`.
- **Issue spam:** deterministic fingerprint plus bounded occurrence updates.
- **Sensitive leakage:** raw evidence local by default; strict sanitization and tests for credential-like content.
- **GitHub outage:** local pending state and later lifecycle retry; no daemon.
- **AI self-modification:** process review cannot create Development Backlog tasks or implementation PRs.
- **Preview churn in `gh-aw`:** retain exact tested pins and existing deterministic source/lock validation.
