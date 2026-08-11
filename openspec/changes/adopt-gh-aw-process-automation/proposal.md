## Why

The current friction-learning path still depends on an agent remembering to record a problem and on a later explicit promotion/review step. That creates exactly the kind of human follow-up the platform is meant to remove. At the same time, GitHub Agentic Workflows (`gh-aw`) now provides a ready-made cloud execution layer for Codex/Claude/Copilot/Gemini inside GitHub Actions, with read-only agent execution, validated safe outputs, schedules, event triggers, sandboxing and cost controls.

The platform should use that existing layer instead of building its own local scheduler, daemon or background review agent. The first version must remain deliberately small and reliable: GitHub Issues are the visible process backlog; local friction storage is only a durable raw/fallback buffer; cloud workflows triage and summarize; humans approve actual platform changes.

## What Changes

- Adopt GitHub Agentic Workflows as an optional additive cloud-maintenance layer for `dev-platform`, using the Codex engine and a repository Actions secret named `OPENAI_API_KEY`.
- Add a narrowly scoped process-issue triage workflow, adapted from the maintained `githubnext/agentics` patterns, that reacts only to process/platform-candidate issues and may label/comment through `safe-outputs` but may not edit code or create implementation PRs.
- Add a periodic process-backlog review workflow (weekly fuzzy schedule plus manual dispatch) that reviews open process issues, identifies likely duplicates/stale/resolved candidates, and creates or refreshes one concise review summary for the human operator.
- Replace the routine manual `promote` expectation with automatic sanitized routing of high-signal friction to the appropriate GitHub backlog: project friction to the current repository, platform friction to `lehard/dev-platform`. Raw evidence remains machine-local by default.
- Add a mandatory completion checkpoint so a non-trivial task cannot silently finish without deciding whether meaningful friction occurred; deterministic lifecycle failures should be captured automatically without relying on model memory.
- Deduplicate repeated friction by a stable sanitized fingerprint so repeated occurrences update one issue rather than creating issue spam.
- Keep an offline/auth-failure fallback: if GitHub issue routing is unavailable, retain the local event and retry routing on a later supported lifecycle invocation rather than losing the observation or blocking safe task completion.
- Put explicit cost/runtime guardrails on every agentic workflow and make workflow failure non-blocking for deterministic CI, publication and release pipelines.
- Pilot this only in `dev-platform`. Do not roll agentic workflows to managed consumer repositories in this change; downstream rollout is a follow-up after the central pilot is proven.
- Preserve a human approval boundary before code-changing remediation. The v1 cloud workflows may triage, research and summarize, but SHALL NOT autonomously modify `dev-platform`, create implementation PRs, approve OpenSpec changes, or merge fixes.

## Capabilities

### New Capabilities

- `agentic-maintenance`: Safe, bounded cloud maintenance using GitHub Agentic Workflows and Codex for process-issue triage and periodic backlog review.

### Modified Capabilities

- `platform-lifecycle`: Make high-signal friction capture and sanitized routing part of ordinary task completion instead of depending on remembered manual promotion.

## Impact

The change affects repository workflows under `.github/workflows/`, platform friction helpers such as `template/scripts/agent_friction.py`, generated agent guidance, completion/doctor integration, tests, and operator setup documentation. The exact `gh-aw` release used for compilation must be pinned and recorded because the project is still in Public Preview.

Implementation sequencing matters: the cloud workflow files and their validation can be developed independently, but any changes to `finish_task.py` or publication/completion integration should be applied only after the active `durable-publication-recovery` work has stabilized, because both changes touch the same lifecycle surface.
