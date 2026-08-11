## Why

The current task lifecycle tells agents to publish completed work, but it does not retain an authoritative publication state or resume an interrupted automatic PR merge. A completed, validated and archived task can therefore remain unmerged until a human remembers to intervene; transient command-output loss and a stale token environment make that failure unnecessarily likely.

## What Changes

- Add a durable, machine-local publication state machine for sealed platform-owned task branches, with safe resume and clear operator status.
- Make automatic PR publication idempotent and single-flight: an interrupted publisher resumes the same branch/PR instead of creating competing publishers or duplicate PRs.
- Resolve GitHub CLI authentication by testing candidate credentials independently, so an invalid exported token cannot hide a valid local GitHub CLI session.
- Make agent completion and doctor guidance report an unfinished sealed publication as an actionable delivery condition rather than a routine warning.
- Add a documented local browser-QA discovery fallback (installed supported browser/cached browser) before declaring Playwright browser validation unavailable.
- Preserve explicit manual review and project-owned lifecycle authority; no arbitrary dirty worktree is auto-published or auto-merged.

## Capabilities

### New Capabilities

- `publication-recovery`: Durable and recoverable automatic publication for a sealed platform-owned task.

### Modified Capabilities

- `platform-lifecycle`: Require resumable, observable completion behavior for platform-owned automatic PR delivery and robust credential selection.
- `completion-lifecycle`: Make unfinished sealed publication visible as incomplete delivery rather than relying on a human hand-off.

## Impact

This affects generated platform-managed scripts and guidance: `finish_task.py`, `project_publish.py`, `_platform_common.py`, `agent_doctor.py`, multi-agent board/cleanup integration, `AGENTS.md`, and engineering workflow/QA documentation. New projects receive the behavior on render; existing platform-owned managed projects receive it through reviewable Copier updates. Project-owned harnesses retain their own publisher, but receive explicit status and integration guidance rather than a silently substituted lifecycle.

Compatibility risks are limited to machine-local state and stricter completion reporting. State must contain no credentials, must be safe to delete/rebuild from GitHub, and must not make a stale or unvalidated branch publishable.
